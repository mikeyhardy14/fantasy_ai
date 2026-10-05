"""Save a Sleeper account token and write the weekly scoring lineup.

The public REST roster can stay cached for minutes after a successful write,
so a lineup is trusted only when the authenticated `matchup_legs` query matches
what was sent. The public matchup payload is still re-read and reported.
"""

import json
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ConflictError,
    NotFoundError,
    ProviderAuthError,
    ProviderError,
    ServiceUnavailableError,
    ValidationFailed,
)
from app.core.logging import get_logger
from app.core.security import CredentialCipher
from app.domain.enums import NON_LINEUP_SLOTS, Provider
from app.intelligence.lineup import eligible_for_ir, is_eligible
from app.models import FantasyAccount, League, RosterEntry
from app.providers.sleeper.graphql import SleeperGraphQL
from app.providers.sleeper.provider import SleeperProvider
from app.repositories import FantasyAccountRepository, RosterRepository, TransactionRepository
from app.schemas.league import (
    AddPlayerRequest,
    ChatTrade,
    ChatTradePlayer,
    ChatTradeSide,
    DirectChatOut,
    LeagueMessageOut,
    LineupUpdateRequest,
    LineupUpdateResponse,
    PlayerOut,
    ProposeTradeResponse,
    RosterMoveRequest,
)
from app.services.league_context import LeagueContextService

log = get_logger(__name__)

EMPTY = "0"


def normalize_sleeper_token(raw: str) -> str:
    token = raw.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in {'"', "'"}:
        token = token[1:-1].strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    parts = token.split(".")
    if not token.startswith("eyJ") or len(parts) != 3 or any(not part for part in parts):
        raise ValidationFailed(
            "That doesn't look like a Sleeper token. In the Sleeper web app open DevTools, "
            "Application, Local Storage, sleeper.com, and copy the value of \"token\"."
        )
    return token


def normalize_starters(starters: list) -> list[str]:
    out: list[str] = []
    for starter in starters:
        if starter is None or str(starter) in {"", "0", "None"}:
            out.append(EMPTY)
        else:
            out.append(str(starter))
    return out


def build_sleeper_write_service(
    session: AsyncSession,
    context: LeagueContextService,
    providers,
    cipher: CredentialCipher,
    graphql_url: str,
) -> "SleeperWriteService":
    sleeper = providers.get(Provider.SLEEPER)
    if not isinstance(sleeper, SleeperProvider):
        raise RuntimeError("Sleeper provider is not configured.")
    return SleeperWriteService(session, context, sleeper, cipher, graphql_url)


class SleeperWriteService:
    def __init__(
        self,
        session: AsyncSession,
        context: LeagueContextService,
        sleeper: SleeperProvider,
        cipher: CredentialCipher,
        graphql_url: str,
    ):
        self.session = session
        self.context = context
        self.sleeper = sleeper
        self.cipher = cipher
        self.graphql_url = graphql_url
        self.accounts = FantasyAccountRepository(session)
        self.rosters = RosterRepository(session)
        self.transactions = TransactionRepository(session)

    async def save_token(self, user_id: UUID, raw_token: str, account_id: UUID | None = None) -> FantasyAccount:
        token = normalize_sleeper_token(raw_token)
        self._require_cipher()
        try:
            identity = await SleeperGraphQL(self.graphql_url, token).whoami()
        except ProviderAuthError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        accounts = await self.accounts.get_by_provider(user_id, Provider.SLEEPER)
        account = self._pick_account(accounts, account_id)
        if account is None:
            raise ValidationFailed("Connect your Sleeper username before saving a token.")
        if account.external_user_id != identity.user_id:
            raise ValidationFailed(
                f"This token belongs to @{identity.username or identity.user_id}, "
                f"but this app is connected to @{account.username}."
            )
        account.encrypted_credentials = self.cipher.encrypt(json.dumps({"token": token}))
        await self.session.commit()
        log.info("sleeper.token_saved", account_id=str(account.id), sleeper_user_id=identity.user_id)
        return account

    async def clear_token(self, user_id: UUID, account_id: UUID | None = None) -> FantasyAccount:
        accounts = await self.accounts.get_by_provider(user_id, Provider.SLEEPER)
        account = self._pick_account(accounts, account_id)
        if account is None:
            raise NotFoundError("No Sleeper account is connected.")
        account.encrypted_credentials = None
        await self.session.commit()
        log.info("sleeper.token_cleared", account_id=str(account.id))
        return account

    async def set_lineup(self, league: League, body: LineupUpdateRequest) -> LineupUpdateResponse:
        if league.provider != Provider.SLEEPER:
            raise ValidationFailed("Lineup edits are only available for Sleeper leagues.")
        if body.week not in {league.current_week, min(18, league.current_week + 1)}:
            raise ValidationFailed(
                f"Only week {league.current_week} or the next week can be edited."
            )
        team = await self.context.user_team(league)
        if team is None:
            raise NotFoundError("We could not find your team in this league.")

        lineup_slots = [slot for slot in league.roster_positions if slot not in NON_LINEUP_SLOTS]
        if len(body.starter_player_ids) != len(lineup_slots):
            raise ValidationFailed(
                f"This league starts {len(lineup_slots)} players. Send one id per slot, or null for an empty slot."
            )

        entries = await self.rosters.list_for_team(team.id, body.week)
        by_id = {entry.player_id: entry for entry in entries}
        seen: set[UUID] = set()
        sleeper_starters: list[str] = []
        for slot, player_id in zip(lineup_slots, body.starter_player_ids, strict=True):
            if player_id is None:
                sleeper_starters.append(EMPTY)
                continue
            if player_id in seen:
                raise ValidationFailed("A player can only fill one starting slot.")
            seen.add(player_id)
            entry = by_id.get(player_id)
            if entry is None:
                raise ValidationFailed("Each starter must already be on your roster.")
            if entry.roster_slot in {"IR", "TAXI"}:
                raise ValidationFailed(f"{entry.player.name} is on {entry.roster_slot} and cannot start.")
            if not is_eligible(_player_view(entry), slot):
                raise ValidationFailed(f"{entry.player.name} is not eligible for {slot}.")
            external_id = entry.player.external_id_for(Provider.SLEEPER)
            if not external_id:
                raise ValidationFailed(f"{entry.player.name} has no Sleeper id, so the lineup cannot be sent.")
            sleeper_starters.append(external_id)

        token = self._token_for(league.fantasy_account)
        graphql = SleeperGraphQL(self.graphql_url, token)
        roster_id = _roster_id(team.external_team_id)
        try:
            await graphql.set_scoring_lineup(
                week=body.week,
                league_id=league.external_league_id,
                roster_id=roster_id,
                starters=sleeper_starters,
            )
        except ProviderAuthError as exc:
            raise ValidationFailed(str(exc.message)) from exc

        try:
            confirmed = await graphql.read_scoring_lineup(
                week=body.week, league_id=league.external_league_id, roster_id=roster_id
            )
        except (ProviderError, ProviderAuthError) as exc:
            log.warning("sleeper.lineup_readback_failed", league_id=league.external_league_id, error=str(exc))
            team_out = await self.context.user_team_out(league, body.week)
            return LineupUpdateResponse(
                team=team_out,
                verified=None,
                public_api_confirmed=None,
                message=(
                    "Sleeper accepted the change, but the scoring lineup could not be re-read. "
                    "Check the Sleeper app before trusting this screen. Nothing was updated here."
                ),
            )

        if confirmed is None or normalize_starters(confirmed) != sleeper_starters:
            raise ConflictError(
                "Sleeper accepted a lineup update that did not change the scoring lineup. "
                "Nothing was saved in this app."
            )

        public_confirmed = await self._public_confirmed(
            league.external_league_id, body.week, team.external_team_id, sleeper_starters
        )
        await self._apply_local(team.id, body.week, entries, lineup_slots, sleeper_starters)
        await self.session.commit()
        log.info(
            "sleeper.lineup_saved",
            league_id=league.external_league_id,
            week=body.week,
            public_api_confirmed=public_confirmed,
        )
        team_out = await self.context.user_team_out(league, body.week)
        return LineupUpdateResponse(
            team=team_out,
            verified=True,
            public_api_confirmed=public_confirmed,
            message=_success_message(public_confirmed),
        )

    async def move_player(self, league: League, body: RosterMoveRequest) -> LineupUpdateResponse:
        """Move one rostered player between a starting slot, the bench, and IR.

        A starter has to leave the scoring lineup before Sleeper will accept them
        on IR. Leaving IR happens before they are written back into a starting slot.
        Each step is confirmed with an authenticated read before the local roster changes.
        """
        if league.provider != Provider.SLEEPER:
            raise ValidationFailed("Lineup edits are only available for Sleeper leagues.")
        if body.week not in {league.current_week, min(18, league.current_week + 1)}:
            raise ValidationFailed(
                f"Only week {league.current_week} or the next week can be edited."
            )
        team = await self.context.user_team(league)
        if team is None:
            raise NotFoundError("We could not find your team in this league.")

        lineup_slots = [slot for slot in league.roster_positions if slot not in NON_LINEUP_SLOTS]
        entries = await self.rosters.list_for_team(team.id, body.week)
        roster = [_seat(entry) for entry in entries]
        seat = next((row for row in roster if row.player_id == body.player_id), None)
        if seat is None:
            raise ValidationFailed("That player is not on your roster.")
        if seat.slot == "TAXI":
            raise ValidationFailed("Taxi squad moves are not available from this screen.")

        starters = _aligned_starters(roster, lineup_slots)
        reserve = [row.external_id for row in roster if row.slot == "IR"]
        desired_starters = starters.copy()
        desired_reserve = reserve.copy()

        if body.destination == "bench":
            if seat.is_starter and seat.slot_index is not None:
                desired_starters[seat.slot_index] = EMPTY
            desired_reserve = [player_id for player_id in desired_reserve if player_id != seat.external_id]
        elif body.destination == "ir":
            if not eligible_for_ir(seat.injury_status, seat.status, league.roster_settings):
                raise ValidationFailed(f"{seat.name} is not eligible for IR.")
            capacity = _ir_capacity(league)
            if capacity <= 0:
                raise ValidationFailed("This league has no IR slots.")
            if seat.external_id not in desired_reserve and len(desired_reserve) >= capacity:
                raise ValidationFailed(
                    f"IR is full ({capacity} {'slot' if capacity == 1 else 'slots'}). Move someone to the bench first."
                )
            if seat.is_starter and seat.slot_index is not None:
                desired_starters[seat.slot_index] = EMPTY
            if seat.external_id not in desired_reserve:
                desired_reserve.append(seat.external_id)
        else:
            index = body.slot_index
            if index is None:
                index = _first_open_slot(lineup_slots, starters, seat)
                if index is None:
                    raise ValidationFailed(
                        f"No open {seat.position or 'roster'} slot. Drop {seat.name} on the starter you want to replace."
                    )
            if index >= len(lineup_slots):
                raise ValidationFailed("That slot is not in this lineup.")
            slot_name = lineup_slots[index]
            if not is_eligible(seat.view, slot_name):
                raise ValidationFailed(f"{seat.name} is not eligible for {slot_name}.")
            if seat.is_starter and seat.slot_index is not None and seat.slot_index != index:
                desired_starters[seat.slot_index] = EMPTY
            desired_starters[index] = seat.external_id
            desired_reserve = [player_id for player_id in desired_reserve if player_id != seat.external_id]

        starters_changed = desired_starters != starters
        reserve_changed = _id_set(desired_reserve) != _id_set(reserve)
        if not starters_changed and not reserve_changed:
            team_out = await self.context.user_team_out(league, body.week)
            return LineupUpdateResponse(
                team=team_out,
                verified=True,
                public_api_confirmed=True,
                message=f"{seat.name} is already there.",
            )

        # Leaving the scoring lineup has to happen before IR will accept a starter.
        # Coming off IR has to happen before that player can be written into a starting slot.
        if body.destination == "starter" and seat.slot == "IR":
            steps = ["reserve", "starters"]
        elif reserve_changed and starters_changed:
            steps = ["starters", "reserve"]
        elif starters_changed:
            steps = ["starters"]
        else:
            steps = ["reserve"]

        token = self._token_for(league.fantasy_account)
        graphql = SleeperGraphQL(self.graphql_url, token)
        roster_id = _roster_id(team.external_team_id)
        applied_starters = starters
        applied_reserve = reserve
        public_starters: bool | None = True
        public_reserve: bool | None = True
        for step in steps:
            try:
                if step == "starters":
                    public_starters = await self._push_starters(
                        graphql, league, body.week, roster_id, desired_starters
                    )
                    applied_starters = desired_starters
                else:
                    public_reserve = await self._push_reserve(graphql, league, roster_id, desired_reserve)
                    applied_reserve = desired_reserve
            except ConflictError:
                raise
            except ProviderAuthError as exc:
                raise ValidationFailed(str(exc.message)) from exc
            except ProviderError as exc:
                if applied_starters != starters or applied_reserve != reserve:
                    await self._apply_placement(
                        team.id, body.week, roster, lineup_slots, applied_starters, set(applied_reserve)
                    )
                    await self.session.commit()
                raise ValidationFailed(str(exc.message)) from exc
            await self._apply_placement(
                team.id, body.week, roster, lineup_slots, applied_starters, set(applied_reserve)
            )
            await self.session.commit()

        confirmed_public = _combine_public(
            public_starters if starters_changed else True,
            public_reserve if reserve_changed else True,
        )
        team_out = await self.context.user_team_out(league, body.week)
        where = {"bench": "on the bench", "ir": "on IR", "starter": "in the starting lineup"}[body.destination]
        return LineupUpdateResponse(
            team=team_out,
            verified=True,
            public_api_confirmed=confirmed_public,
            message=_move_message(seat.name, where, confirmed_public),
        )

    async def league_messages(self, league: League, limit: int = 80) -> list[LeagueMessageOut]:
        """Messages on the league board, oldest first. Private threads are not included."""
        graphql = self._chat_client(league, "League chat is available for Sleeper leagues.", "read the league chat.")
        try:
            rows = await graphql.league_messages(league.external_league_id)
        except ProviderAuthError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        except ProviderError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        return _chat_messages(rows, user_id=league.fantasy_account.external_user_id)[-limit:]

    async def direct_chats(self, league: League) -> list[DirectChatOut]:
        """Other managers in this league, with the direct thread when one exists."""
        graphql = self._chat_client(league, "Direct chat is available for Sleeper leagues.", "read chats with other managers.")
        me = league.fantasy_account.external_user_id
        teams = [
            team
            for team in await self.context.teams.list_for_league(league.id)
            if team.owner_external_id and team.owner_external_id != me
        ]
        by_owner = {team.owner_external_id: team for team in teams}
        try:
            threads = await graphql.my_dms()
        except ProviderAuthError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        except ProviderError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        thread_for: dict[str, tuple[str, datetime | None]] = {}
        for thread in threads:
            others = [user_id for user_id in _dm_user_ids(thread) if user_id != me and user_id in by_owner]
            if len(others) != 1:
                continue
            when = _millis(thread.get("last_message_time"))
            owner = others[0]
            current = thread_for.get(owner)
            if current is None or (when and (current[1] is None or when > current[1])):
                thread_for[owner] = (str(thread.get("dm_id")), when)
        chats = [
            DirectChatOut(
                user_id=str(team.owner_external_id),
                name=team.owner_name or team.name,
                team_name=team.name,
                thread_id=thread_for[team.owner_external_id][0] if team.owner_external_id in thread_for else None,
                last_message_at=thread_for[team.owner_external_id][1] if team.owner_external_id in thread_for else None,
            )
            for team in teams
        ]
        chats.sort(key=lambda chat: (chat.last_message_at is None, -(chat.last_message_at.timestamp() if chat.last_message_at else 0), chat.name.lower()))
        return chats

    async def direct_messages(self, league: League, thread_id: str, limit: int = 80) -> list[LeagueMessageOut]:
        graphql = self._chat_client(league, "Direct chat is available for Sleeper leagues.", "read chats with other managers.")
        await self._require_league_thread(league, graphql, thread_id)
        try:
            rows = await graphql.thread_messages(thread_id)
        except ProviderAuthError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        except ProviderError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        return _chat_messages(rows, user_id=league.fantasy_account.external_user_id)[-limit:]

    async def send_direct(
        self, league: League, text: str, thread_id: str | None = None, user_id: str | None = None
    ) -> tuple[str, list[LeagueMessageOut]]:
        """Send a message in a thread with one manager from this league."""
        graphql = self._chat_client(league, "Direct chat is available for Sleeper leagues.", "message other managers.")
        if thread_id:
            await self._require_league_thread(league, graphql, thread_id)
        elif user_id:
            thread_id = await self._open_thread(league, graphql, user_id)
        else:
            raise ValidationFailed("Choose a manager to message.")
        try:
            await graphql.send_message(thread_id, "dm", text.strip())
            rows = await graphql.thread_messages(thread_id)
        except ProviderAuthError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        except ProviderError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        return thread_id, _chat_messages(rows, user_id=league.fantasy_account.external_user_id)

    async def respond_to_trade(self, league: League, transaction_id: str, action: str) -> str:
        """Accept or decline a pending offer that includes this manager."""
        if action not in {"accept", "decline"}:
            raise ValidationFailed("Choose accept or decline.")
        graphql = self._chat_client(league, "Responding to a trade is only available for Sleeper leagues.", "respond to a trade.")
        try:
            rows = await graphql.league_messages(league.external_league_id)
        except ProviderAuthError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        except ProviderError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        me = league.fantasy_account.external_user_id
        offer = next(
            (
                trade
                for row in rows
                if (trade := _trade_card(row.get("attachment"), me))
                and trade.involves_user
                and trade.transaction_id == transaction_id
                and trade.status == "pending"
            ),
            None,
        )
        if offer is None:
            raise ValidationFailed("That offer is not a pending trade that includes you.")
        try:
            result = await graphql.respond_trade(
                league_id=league.external_league_id,
                transaction_id=transaction_id,
                week=league.current_week,
                accept=action == "accept",
            )
        except ProviderAuthError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        except ProviderError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        status = str(result.get("status") or ("complete" if action == "accept" else "rejected"))
        if action == "accept":
            return f"You accepted the trade. Sleeper marked it {status}."
        return f"You declined the trade. Sleeper marked it {status}."

    def _chat_client(self, league: League, wrong_provider: str, missing_token: str) -> SleeperGraphQL:
        if league.provider != Provider.SLEEPER:
            raise ValidationFailed(wrong_provider)
        if not league.fantasy_account.encrypted_credentials:
            raise ValidationFailed(f"Save your Sleeper token in Settings to {missing_token}")
        return SleeperGraphQL(self.graphql_url, self._token_for(league.fantasy_account))

    async def _require_league_thread(self, league: League, graphql: SleeperGraphQL, thread_id: str) -> None:
        me = league.fantasy_account.external_user_id
        owners = {
            team.owner_external_id
            for team in await self.context.teams.list_for_league(league.id)
            if team.owner_external_id and team.owner_external_id != me
        }
        try:
            threads = await graphql.my_dms()
        except ProviderAuthError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        except ProviderError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        for thread in threads:
            if str(thread.get("dm_id")) != thread_id:
                continue
            others = [user_id for user_id in _dm_user_ids(thread) if user_id != me]
            if len(others) == 1 and others[0] in owners:
                return
            break
        raise ValidationFailed("That conversation is not with a manager in this league.")

    async def _open_thread(self, league: League, graphql: SleeperGraphQL, user_id: str) -> str:
        me = league.fantasy_account.external_user_id
        if user_id == me:
            raise ValidationFailed("Pick another manager.")
        owners = {
            team.owner_external_id
            for team in await self.context.teams.list_for_league(league.id)
            if team.owner_external_id
        }
        if user_id not in owners:
            raise ValidationFailed("That person is not a manager in this league.")
        try:
            threads = await graphql.my_dms()
        except ProviderAuthError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        except ProviderError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        for thread in threads:
            others = [owner for owner in _dm_user_ids(thread) if owner != me]
            if others == [user_id] and thread.get("dm_id"):
                return str(thread["dm_id"])
        try:
            return await graphql.create_dm(user_id)
        except ProviderAuthError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        except ProviderError as exc:
            raise ValidationFailed(str(exc.message)) from exc

    async def propose_trade(self, league: League, give: list[UUID], receive: list[UUID]) -> ProposeTradeResponse:
        """Send a player trade offer to one other manager. It is not accepted here."""
        if league.provider != Provider.SLEEPER:
            raise ValidationFailed("Proposing a trade is only available for Sleeper leagues.")
        if len(set(give)) != len(give) or len(set(receive)) != len(receive):
            raise ValidationFailed("Each player can only be in the offer once.")
        if set(give) & set(receive):
            raise ValidationFailed("A player cannot be on both sides of the offer.")
        deadline = league.league_settings.get("trade_deadline")
        if deadline is not None and league.current_week > int(deadline):
            raise ValidationFailed(f"The trade deadline was week {deadline}.")
        team = await self.context.user_team(league)
        if team is None:
            raise NotFoundError("We could not find your team in this league.")
        rostered = await self.rosters.list_for_league(league.id, league.current_week)
        by_player: dict[UUID, RosterEntry] = {}
        for entry in rostered:
            by_player.setdefault(entry.player_id, entry)

        give_entries: list[RosterEntry] = []
        for player_id in give:
            entry = by_player.get(player_id)
            if entry is None or entry.fantasy_team_id != team.id:
                raise ValidationFailed("You can only trade away players on your roster.")
            give_entries.append(entry)

        receive_entries: list[RosterEntry] = []
        owners: set[UUID] = set()
        for player_id in receive:
            entry = by_player.get(player_id)
            if entry is None:
                raise ValidationFailed("Receive players who are on a roster in this league.")
            if entry.fantasy_team_id == team.id:
                raise ValidationFailed("You already have one of the players you want to receive.")
            owners.add(entry.fantasy_team_id)
            receive_entries.append(entry)
        if len(owners) != 1:
            raise ValidationFailed("Receive players from one team. An offer goes to one manager.")

        opponent = await self.context.teams.get(league.id, next(iter(owners)))
        if opponent is None:
            raise NotFoundError("We could not find that team in this league.")
        if not league.fantasy_account.encrypted_credentials:
            raise ValidationFailed("Save your Sleeper token in Settings before sending a trade.")
        token = self._token_for(league.fantasy_account)
        graphql = SleeperGraphQL(self.graphql_url, token)
        try:
            tx = await graphql.propose_trade(
                league_id=league.external_league_id,
                my_roster_id=_roster_id(team.external_team_id),
                their_roster_id=_roster_id(opponent.external_team_id),
                give_player_ids=[_sleeper_id(entry) for entry in give_entries],
                receive_player_ids=[_sleeper_id(entry) for entry in receive_entries],
            )
        except ProviderAuthError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        except ProviderError as exc:
            raise ValidationFailed(str(exc.message)) from exc

        status = str(tx.get("status") or "pending")
        if tx.get("transaction_id"):
            await self.transactions.upsert(
                league_id=league.id,
                external_transaction_id=str(tx["transaction_id"]),
                type="trade",
                status=status,
                week=league.current_week,
                created_at=datetime.now(UTC),
                details={
                    "adds": [_trade_player(entry, team) for entry in receive_entries]
                    + [_trade_player(entry, opponent) for entry in give_entries],
                    "drops": [_trade_player(entry, team) for entry in give_entries]
                    + [_trade_player(entry, opponent) for entry in receive_entries],
                    "team_ids": [str(team.id), str(opponent.id)],
                    "team_names": [team.name, opponent.name],
                    "faab_bid": None,
                    "draft_picks": [],
                },
            )
            await self.session.commit()
        sent = ", ".join(entry.player.name for entry in give_entries)
        got = ", ".join(entry.player.name for entry in receive_entries)
        return ProposeTradeResponse(
            message=f"Offer sent to {opponent.name}: {sent} for {got}. They accept it in Sleeper.",
            status=status,
            transaction_id=str(tx["transaction_id"]) if tx.get("transaction_id") else None,
            opponent_name=opponent.name,
        )

    async def add_player(self, league: League, body: AddPlayerRequest) -> LineupUpdateResponse:
        """Add a free agent, drop a rostered player, or do both."""
        if league.provider != Provider.SLEEPER:
            raise ValidationFailed("Adding a player is only available for Sleeper leagues.")
        if body.player_id is None and body.drop_player_id is None:
            raise ValidationFailed("Choose a player to add or a player to drop.")
        week = league.current_week
        team = await self.context.user_team(league)
        if team is None:
            raise NotFoundError("We could not find your team in this league.")
        player = None
        external_id = None
        rostered = await self.rosters.list_for_league(league.id, week)
        if body.player_id is not None:
            player = await self.context.players.get(body.player_id)
            if player is None:
                raise NotFoundError("Player not found.")
            external_id = player.external_id_for(Provider.SLEEPER)
            if not external_id:
                raise ValidationFailed(f"{player.name} has no Sleeper id, so they cannot be added.")
            if any(entry.player_id == player.id for entry in rostered):
                raise ValidationFailed(f"Someone already has {player.name}.")
        mine = [entry for entry in rostered if entry.fantasy_team_id == team.id]
        drop_entry: RosterEntry | None = None
        drop_external: str | None = None
        if body.drop_player_id is not None:
            if player is not None and body.drop_player_id == player.id:
                raise ValidationFailed("Choose someone else to drop.")
            drop_entry = next((entry for entry in mine if entry.player_id == body.drop_player_id), None)
            if drop_entry is None:
                raise ValidationFailed("That player is not on your roster.")
            drop_external = drop_entry.player.external_id_for(Provider.SLEEPER)
            if not drop_external:
                raise ValidationFailed(f"{drop_entry.player.name} has no Sleeper id, so they cannot be dropped.")
        elif player is not None:
            cap = league.roster_settings.get("max_roster_size")
            if cap is not None and len(mine) >= int(cap):
                raise ValidationFailed("Your roster is full. Choose someone to drop.")

        token = self._token_for(league.fantasy_account)
        graphql = SleeperGraphQL(self.graphql_url, token)
        roster_id = _roster_id(team.external_team_id)
        try:
            tx = await graphql.add_free_agent(
                league_id=league.external_league_id,
                roster_id=roster_id,
                week=week,
                player_id=external_id,
                drop_player_id=drop_external,
            )
        except ProviderAuthError as exc:
            raise ValidationFailed(str(exc.message)) from exc
        except ProviderError as exc:
            raise ValidationFailed(str(exc.message)) from exc

        status = str(tx.get("status") or "complete").lower()
        if status in {"pending", "failed", "rejected", "cancelled", "canceled"}:
            team_out = await self.context.user_team_out(league, week)
            waiting = status == "pending"
            if waiting and player is not None and drop_entry is not None:
                message = (
                    f"Sleeper has a claim in for {player.name} and drop {drop_entry.player.name}. "
                    "They join your roster when it clears."
                )
            elif waiting and player is not None:
                message = f"Sleeper has a claim in for {player.name}. They join your roster when it clears."
            elif waiting and drop_entry is not None:
                message = f"Sleeper has a claim in to drop {drop_entry.player.name}. It clears with waivers."
            else:
                who = player.name if player is not None else drop_entry.player.name if drop_entry else "that player"
                message = f"Sleeper did not change the roster for {who} ({status})."
            return LineupUpdateResponse(
                team=team_out,
                verified=False,
                public_api_confirmed=False,
                message=message,
            )

        dropped_name = drop_entry.player.name if drop_entry is not None else None
        if drop_entry is not None:
            await self.session.delete(drop_entry)
        if player is not None:
            self.session.add(
                RosterEntry(
                    fantasy_team_id=team.id,
                    player_id=player.id,
                    week=week,
                    roster_slot="BN",
                    is_starter=False,
                    slot_index=None,
                )
            )
        await self.session.commit()
        if external_id:
            public = await self._public_has_player(league.external_league_id, roster_id, external_id)
        elif drop_external:
            still_there = await self._public_has_player(league.external_league_id, roster_id, drop_external)
            public = None if still_there is None else not still_there
        else:
            public = None
        team_out = await self.context.user_team_out(league, week)
        if player is not None:
            lead = f"{player.name} is on your bench."
            if dropped_name:
                lead = f"Dropped {dropped_name}. {lead}"
        else:
            lead = f"Dropped {dropped_name}."
        verb = "add" if player is not None else "drop"
        if public is True:
            message = f"{lead} The public roster matches."
        elif public is False:
            message = (
                f"{lead} Sleeper confirmed the {verb}. The public roster API still shows the previous roster; "
                "it is cached and can lag for a few minutes."
            )
        else:
            message = f"{lead} Sleeper confirmed the {verb}. The public roster API could not be re-read."
        return LineupUpdateResponse(
            team=team_out,
            verified=True,
            public_api_confirmed=public,
            message=message,
        )

    async def _public_has_player(self, league_id: str, roster_id: int, player_id: str) -> bool | None:
        try:
            rosters = await self.sleeper.client.get_rosters(league_id)
        except ProviderError:
            return None
        for roster in rosters:
            if str(roster.get("roster_id")) != str(roster_id):
                continue
            players = roster.get("players") or []
            return str(player_id) in {str(item) for item in players}
        return False

    async def _push_starters(
        self,
        graphql: SleeperGraphQL,
        league: League,
        week: int,
        roster_id: int,
        starters: list[str],
    ) -> bool | None:
        await graphql.set_scoring_lineup(
            week=week,
            league_id=league.external_league_id,
            roster_id=roster_id,
            starters=starters,
        )
        try:
            confirmed = await graphql.read_scoring_lineup(
                week=week, league_id=league.external_league_id, roster_id=roster_id
            )
        except (ProviderError, ProviderAuthError) as exc:
            log.warning("sleeper.lineup_readback_failed", league_id=league.external_league_id, error=str(exc))
            raise ValidationFailed(
                "Sleeper accepted the lineup change, but the scoring lineup could not be re-read. "
                "Check the Sleeper app. Nothing further was saved here."
            ) from exc
        if confirmed is None or normalize_starters(confirmed) != starters:
            raise ConflictError(
                "Sleeper accepted a lineup update that did not change the scoring lineup. "
                "Nothing was saved in this app."
            )
        return await self._public_confirmed(league.external_league_id, week, str(roster_id), starters)

    async def _push_reserve(
        self,
        graphql: SleeperGraphQL,
        league: League,
        roster_id: int,
        reserve: list[str],
    ) -> bool | None:
        await graphql.set_reserve(league_id=league.external_league_id, roster_id=roster_id, reserve=reserve)
        try:
            confirmed = await graphql.read_reserve(league_id=league.external_league_id, roster_id=roster_id)
        except (ProviderError, ProviderAuthError) as exc:
            log.warning("sleeper.reserve_readback_failed", league_id=league.external_league_id, error=str(exc))
            raise ValidationFailed(
                "Sleeper accepted the IR change, but the reserve list could not be re-read. "
                "Check the Sleeper app before trusting this screen."
            ) from exc
        if confirmed is None or _id_set(confirmed) != _id_set(reserve):
            raise ConflictError(
                "Sleeper accepted an IR update that did not change the reserve list. Nothing further was saved here."
            )
        return await self._public_reserve(league.external_league_id, str(roster_id), reserve)

    def _require_cipher(self) -> None:
        if not self.cipher.enabled:
            raise ServiceUnavailableError("Set CREDENTIALS_KEY before saving a Sleeper token.")

    def _token_for(self, account: FantasyAccount) -> str:
        if not account.encrypted_credentials:
            raise ValidationFailed("Save your Sleeper token in Settings before editing a lineup.")
        self._require_cipher()
        try:
            payload = json.loads(self.cipher.decrypt(account.encrypted_credentials))
            token = payload["token"]
        except (RuntimeError, KeyError, json.JSONDecodeError) as exc:
            raise ServiceUnavailableError(
                "The stored Sleeper token could not be read. Paste it again in Settings."
            ) from exc
        if not isinstance(token, str) or not token:
            raise ServiceUnavailableError("The stored Sleeper token could not be read. Paste it again in Settings.")
        return token

    def _pick_account(self, accounts: list[FantasyAccount], account_id: UUID | None) -> FantasyAccount | None:
        if account_id is not None:
            return next((account for account in accounts if account.id == account_id), None)
        if len(accounts) == 1:
            return accounts[0]
        if len(accounts) > 1:
            raise ValidationFailed("More than one Sleeper account is connected. Choose which one this token is for.")
        return None

    async def _public_confirmed(
        self, league_id: str, week: int, roster_id: str, expected: list[str]
    ) -> bool | None:
        try:
            matchups = await self.sleeper.client.get_matchups(league_id, week)
        except ProviderError as exc:
            log.warning("sleeper.public_lineup_read_failed", league_id=league_id, error=str(exc))
            return None
        for row in matchups:
            if str(row.get("roster_id")) != str(roster_id):
                continue
            starters = row.get("starters")
            if not isinstance(starters, list):
                return None
            return normalize_starters(starters) == expected
        return None

    async def _public_reserve(self, league_id: str, roster_id: str, expected: list[str]) -> bool | None:
        try:
            rosters = await self.sleeper.client.get_rosters(league_id)
        except ProviderError as exc:
            log.warning("sleeper.public_reserve_read_failed", league_id=league_id, error=str(exc))
            return None
        for row in rosters:
            if str(row.get("roster_id")) != str(roster_id):
                continue
            reserve = row.get("reserve") or []
            if not isinstance(reserve, list):
                return None
            return _id_set(reserve) == _id_set(expected)
        return None

    async def _apply_placement(
        self,
        team_id: UUID,
        week: int,
        roster: list["_Seat"],
        lineup_slots: list[str],
        sleeper_starters: list[str],
        reserve_ids: set[str],
    ) -> None:
        by_external = {row.external_id: row for row in roster}
        replacement: list[tuple[UUID, str, bool, int | None]] = []
        used: set[UUID] = set()
        for index, external_id in enumerate(sleeper_starters):
            if external_id == EMPTY:
                continue
            row = by_external[external_id]
            replacement.append((row.player_id, lineup_slots[index], True, index))
            used.add(row.player_id)
        for row in roster:
            if row.player_id in used:
                continue
            if row.external_id in reserve_ids:
                slot = "IR"
            elif row.slot == "TAXI":
                slot = "TAXI"
            else:
                slot = "BN"
            replacement.append((row.player_id, slot, False, None))
        await self.rosters.replace_for_team(team_id, week, replacement)

    async def _apply_local(
        self,
        team_id: UUID,
        week: int,
        entries: list[RosterEntry],
        lineup_slots: list[str],
        sleeper_starters: list[str],
    ) -> None:
        by_external: dict[str, RosterEntry] = {}
        for entry in entries:
            external_id = entry.player.external_id_for(Provider.SLEEPER)
            if external_id:
                by_external[external_id] = entry
        used: set[UUID] = set()
        replacement: list[tuple[UUID, str, bool, int | None]] = []
        for index, external_id in enumerate(sleeper_starters):
            if external_id == EMPTY:
                continue
            entry = by_external[external_id]
            replacement.append((entry.player_id, lineup_slots[index], True, index))
            used.add(entry.player_id)
        for entry in entries:
            if entry.player_id in used:
                continue
            slot = entry.roster_slot if entry.roster_slot in {"IR", "TAXI"} else "BN"
            replacement.append((entry.player_id, slot, False, None))
        await self.rosters.replace_for_team(team_id, week, replacement)


def _player_view(entry: RosterEntry) -> PlayerOut:
    player = entry.player
    return PlayerOut(
        id=player.id,
        name=player.name,
        position=player.position,
        fantasy_positions=list(player.fantasy_positions or []),
        nfl_team=player.nfl_team,
    )


def _dm_user_ids(thread: dict) -> list[str]:
    users = thread.get("recent_users") or []
    if isinstance(users, str):
        try:
            users = json.loads(users)
        except ValueError:
            return []
    if not isinstance(users, list):
        return []
    return [str(user.get("user_id")) for user in users if isinstance(user, dict) and user.get("user_id")]


def _millis(value) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)


_MENTION = re.compile(r"<@([^>]+)>")


def _plain_text(text: str) -> str:
    return _MENTION.sub(lambda match: f"@{match.group(1)}", text).strip()


def _player_name(raw: dict) -> ChatTradePlayer | None:
    first = str(raw.get("first_name") or "").strip()
    last = str(raw.get("last_name") or "").strip()
    name = str(raw.get("full_name") or " ".join(part for part in (first, last) if part)).strip()
    if not name:
        return None
    position = raw.get("position")
    player_id = raw.get("player_id")
    headshot = (
        f"https://sleepercdn.com/content/nfl/players/{player_id}.jpg"
        if player_id and str(player_id).isdigit()
        else None
    )
    return ChatTradePlayer(name=name, position=str(position) if position else None, headshot_url=headshot)


def _pick_label(raw: object) -> str | None:
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if not isinstance(raw, dict):
        return None
    season = raw.get("season")
    rnd = raw.get("round")
    if season and rnd:
        return f"{season} round {rnd}"
    if rnd:
        return f"round {rnd}"
    return None


def _trade_card(attachment: object, user_id: str | None) -> ChatTrade | None:
    if not isinstance(attachment, dict) or attachment.get("type") != "transactions":
        return None
    data = attachment.get("data") or []
    item = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else None
    if item is None or item.get("type") != "trade":
        return None
    by_roster = item.get("transactions_by_roster") or {}
    if not isinstance(by_roster, dict):
        return None
    sides: list[ChatTradeSide] = []
    status = "pending"
    involves_user = False
    for side in by_roster.values():
        if not isinstance(side, dict):
            continue
        status = str(side.get("status") or status)
        user = side.get("user") if isinstance(side.get("user"), dict) else {}
        if user_id and str(user.get("user_id") or "") == user_id:
            involves_user = True
        receives = [player for raw in side.get("adds") or [] if isinstance(raw, dict) and (player := _player_name(raw))]
        picks = [label for raw in side.get("added_picks") or [] if (label := _pick_label(raw))]
        if not receives and not picks:
            continue
        sides.append(
            ChatTradeSide(
                manager=str(user.get("display_name") or "Manager"),
                receives=receives,
                picks=picks,
            )
        )
    if not sides:
        return None
    return ChatTrade(
        status=status,
        transaction_id=str(item["transaction_id"]) if item.get("transaction_id") else None,
        involves_user=involves_user,
        sides=sides,
    )


def _name_list(parts: list[str]) -> str:
    names = [part for part in parts if part]
    if not names:
        return "nothing"
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _trade_text(trade: ChatTrade) -> str:
    """Say which players moved, so the line is the offer and not only that one exists."""
    if len(trade.sides) == 1:
        side = trade.sides[0]
        got = _name_list([player.name for player in side.receives] + side.picks)
        verb = "would receive" if trade.status == "pending" else "received"
        return f"{side.manager} {verb} {got}"
    first, second = trade.sides[0], trade.sides[1]
    first_gets = _name_list([player.name for player in first.receives] + first.picks)
    second_gets = _name_list([player.name for player in second.receives] + second.picks)
    if trade.status == "pending":
        return f"{first.manager} offered {second_gets} to {second.manager} for {first_gets}"
    if trade.status == "complete":
        return f"{first.manager} traded {second_gets} to {second.manager} for {first_gets}"
    return f"{first.manager} and {second.manager} updated a trade: {second_gets} for {first_gets}"


def _chat_messages(rows: list[dict], user_id: str | None) -> list[LeagueMessageOut]:
    messages: list[LeagueMessageOut] = []
    for row in rows:
        author_name = str(row.get("author_display_name") or "Manager")
        trade = _trade_card(row.get("attachment"), user_id)
        if trade is not None and not trade.involves_user:
            continue
        text = _trade_text(trade) if trade is not None else _plain_text(str(row.get("text") or ""))
        if not text:
            continue
        when = _millis(row.get("created")) or datetime.now(UTC)
        author_id = str(row.get("author_id") or "")
        messages.append(
            LeagueMessageOut(
                id=str(row.get("message_id") or when.timestamp()),
                author_name=author_name,
                text=text,
                created_at=when,
                pinned=bool(row.get("pinned")),
                mine=bool(user_id and author_id == user_id),
                trade=trade,
            )
        )
    messages.sort(key=lambda item: item.created_at)
    return messages


def _trade_player(entry: RosterEntry, team) -> dict:
    return {
        "player_id": str(entry.player_id),
        "player_name": entry.player.name,
        "position": entry.player.position,
        "team_id": str(team.id),
        "team_name": team.name,
    }


def _sleeper_id(entry: RosterEntry) -> str:
    external = entry.player.external_id_for(Provider.SLEEPER)
    if not external:
        raise ValidationFailed(f"{entry.player.name} has no Sleeper id, so they cannot be traded.")
    return external


def _roster_id(external_team_id: str) -> int:
    try:
        return int(external_team_id)
    except (TypeError, ValueError) as exc:
        raise ValidationFailed("This roster has no Sleeper roster id, so the lineup cannot be sent.") from exc


class _Seat:
    def __init__(self, entry: RosterEntry):
        player = entry.player
        external_id = player.external_id_for(Provider.SLEEPER)
        if not external_id:
            raise ValidationFailed(f"{player.name} has no Sleeper id, so the lineup cannot be sent.")
        self.player_id = entry.player_id
        self.external_id = external_id
        self.name = player.name
        self.position = player.position
        self.slot = entry.roster_slot
        self.is_starter = entry.is_starter
        self.slot_index = entry.slot_index
        self.view = _player_view(entry)
        self.injury_status = player.injury_status
        self.status = player.status


def _seat(entry: RosterEntry) -> _Seat:
    return _Seat(entry)


def _aligned_starters(roster: list[_Seat], lineup_slots: list[str]) -> list[str]:
    starters = [EMPTY] * len(lineup_slots)
    for row in roster:
        if row.is_starter and row.slot_index is not None and 0 <= row.slot_index < len(lineup_slots):
            starters[row.slot_index] = row.external_id
    return starters


def _ir_capacity(league: League) -> int:
    from_positions = league.roster_positions.count("IR")
    raw = league.roster_settings.get("reserve_slots") or 0
    try:
        from_settings = int(raw)
    except (TypeError, ValueError):
        from_settings = 0
    return max(from_positions, from_settings)


def _first_open_slot(lineup_slots: list[str], starters: list[str], seat: _Seat) -> int | None:
    for index, slot in enumerate(lineup_slots):
        if starters[index] != EMPTY:
            continue
        if is_eligible(seat.view, slot):
            return index
    return None


def _id_set(player_ids: list[str]) -> list[str]:
    return sorted(str(player_id) for player_id in player_ids if str(player_id) not in {"", "0", "None"})


def _combine_public(starters_public: bool | None, reserve_public: bool | None) -> bool | None:
    flags = [starters_public, reserve_public]
    if any(flag is False for flag in flags):
        return False
    if any(flag is None for flag in flags):
        return None
    return True


def _move_message(name: str, where: str, public_confirmed: bool | None) -> str:
    lead = f"{name} is now {where}."
    if public_confirmed is True:
        return f"{lead} Sleeper's scoring lineup and the public roster API both match."
    if public_confirmed is False:
        return (
            f"{lead} Sleeper confirmed the change. The public roster API still shows the previous roster; "
            "it is cached and can lag for a few minutes."
        )
    return f"{lead} Sleeper confirmed the change. The public roster API could not be re-read."


def _success_message(public_confirmed: bool | None) -> str:
    if public_confirmed is True:
        return "Lineup saved. Sleeper's scoring lineup and the public roster API both match what you sent."
    if public_confirmed is False:
        return (
            "Lineup saved. Sleeper's scoring lineup matches what you sent. "
            "The public roster API still shows the previous lineup; it is cached and can lag for a few minutes."
        )
    return "Lineup saved and confirmed on Sleeper's scoring lineup. The public roster API could not be re-read."
