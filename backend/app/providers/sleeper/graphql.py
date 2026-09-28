"""Authenticated client for the Sleeper web app's private GraphQL API.

Sleeper publishes no schema docs. The scoring lineup is `update_matchup_leg`.
`roster_update_starters` persists and returns success without changing what
scores, so this client never calls it.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.errors import ProviderAuthError, ProviderError, ProviderUnavailable
from app.core.logging import get_logger

log = get_logger(__name__)

WHOAMI_QUERY = "query { me { user_id username display_name } }"

SET_SCORING_LINEUP = """
mutation($round: Int!, $leg: Int!, $league_id: Snowflake!, $roster_id: Int!, $starters: [String]) {
  update_matchup_leg(round: $round, leg: $leg, league_id: $league_id, roster_id: $roster_id, starters: $starters) {
    roster_id
    starters
  }
}
""".strip()

READ_SCORING_LINEUPS = """
query($round: Int!, $league_id: Snowflake!) {
  matchup_legs(round: $round, league_id: $league_id) {
    roster_id
    starters
  }
}
""".strip()

# IR is the roster reserve list, not a scoring-lineup slot. This is the mutation
# the Sleeper app uses. It is not roster_update_starters.
SET_RESERVE = """
mutation($league_id: Snowflake!, $roster_id: Int!, $reserve: [String]) {
  roster_update_reserve(league_id: $league_id, roster_id: $roster_id, reserve: $reserve) {
    roster_id
    reserve
  }
}
""".strip()

PROPOSE_TRADE = """
mutation($league_id: Snowflake!, $k_adds: [String], $v_adds: [Int], $k_drops: [String], $v_drops: [Int], $waiver_budget: [String]) {
  propose_trade(
    league_id: $league_id
    k_adds: $k_adds
    v_adds: $v_adds
    k_drops: $k_drops
    v_drops: $v_drops
    waiver_budget: $waiver_budget
  ) {
    transaction_id
    status
  }
}
""".strip()

ADD_FREE_AGENT = """
mutation($league_id: Snowflake!, $roster_id: Int!, $leg: Int!, $adds: [Map]!, $drops: [Map]!) {
  league_create_roster_transaction(
    league_id: $league_id
    type: "free_agent"
    roster_id: $roster_id
    leg: $leg
    adds: $adds
    drops: $drops
  ) {
    transaction_id
    status
    adds
    drops
  }
}
""".strip()

LEAGUE_MESSAGES = """
query($parent_id: String!) {
  messages(parent_id: $parent_id) {
    message_id
    created
    author_id
    author_display_name
    text
    attachment
    pinned
  }
}
""".strip()

MY_DMS = """
query {
  my_dms {
    dm_id
    title
    dm_type
    last_message_time
    recent_users
  }
}
""".strip()

CREATE_DM = """
mutation($dm_type: String!, $members: [Snowflake!]!) {
  create_dm(dm_type: $dm_type, members: $members) {
    dm_id
  }
}
""".strip()

ACCEPT_TRADE = """
mutation($leg: Int!, $league_id: Snowflake!, $transaction_id: Snowflake!) {
  accept_trade(leg: $leg, league_id: $league_id, transaction_id: $transaction_id) {
    transaction_id
    status
  }
}
""".strip()

REJECT_TRADE = """
mutation($leg: Int!, $league_id: Snowflake!, $transaction_id: Snowflake!) {
  reject_trade(leg: $leg, league_id: $league_id, transaction_id: $transaction_id) {
    transaction_id
    status
  }
}
""".strip()

CREATE_MESSAGE = """
mutation($parent_id: Snowflake!, $parent_type: String!, $text: String!) {
  create_message(parent_id: $parent_id, parent_type: $parent_type, text: $text) {
    message_id
  }
}
""".strip()

READ_ROSTERS = """
query($league_id: Snowflake!) {
  league_rosters(league_id: $league_id) {
    roster_id
    reserve
    starters
  }
}
""".strip()

USER_AGENT = "fantasy-ai/0.1 (+https://github.com)"


@dataclass(frozen=True)
class SleeperIdentity:
    user_id: str
    username: str
    display_name: str | None


class SleeperGraphQL:
    def __init__(self, url: str, token: str | None = None, timeout: float = 15.0):
        self.url = url
        self.token = token
        self.timeout = timeout

    async def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        # The web app sends the raw JWT. A "Bearer " prefix is rejected.
        if self.token:
            headers["Authorization"] = self.token
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.url, json={"query": query, "variables": variables or {}}, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            log.warning("sleeper.graphql_transport_error", error=type(exc).__name__)
            raise ProviderUnavailable("Could not reach Sleeper.", provider="sleeper") from exc

        if resp.status_code in (401, 403):
            raise ProviderAuthError(
                "Sleeper rejected the token. Paste a fresh one from the web app.", provider="sleeper"
            )
        if resp.status_code >= 400:
            raise ProviderUnavailable(f"Sleeper returned HTTP {resp.status_code}.", provider="sleeper")
        try:
            body = resp.json()
        except ValueError as exc:
            raise ProviderUnavailable("Sleeper returned an unreadable response.", provider="sleeper") from exc
        if not isinstance(body, dict):
            raise ProviderError("Sleeper returned an unreadable response.", provider="sleeper")

        errors = body.get("errors") or []
        if errors:
            message = _error_message(errors)
            lowered = message.lower()
            if any(phrase in lowered for phrase in ("unauthorized", "not authenticated", "invalid token")):
                raise ProviderAuthError(
                    "Sleeper rejected the token. Paste a fresh one from the web app.", provider="sleeper"
                )
            raise ProviderError(message or "Sleeper rejected the request.", provider="sleeper")

        data = body.get("data")
        if not isinstance(data, dict):
            raise ProviderError("Sleeper returned an empty response.", provider="sleeper")
        return data

    async def whoami(self) -> SleeperIdentity:
        data = await self.execute(WHOAMI_QUERY)
        me = data.get("me")
        if not isinstance(me, dict) or not me.get("user_id"):
            raise ProviderAuthError(
                "Sleeper rejected the token. Paste a fresh one from the web app.", provider="sleeper"
            )
        return SleeperIdentity(
            user_id=str(me["user_id"]),
            username=str(me.get("username") or ""),
            display_name=me.get("display_name"),
        )

    async def set_scoring_lineup(
        self, *, week: int, league_id: str, roster_id: int, starters: list[str]
    ) -> None:
        await self.execute(
            SET_SCORING_LINEUP,
            {
                "round": week,
                "leg": week,
                "league_id": league_id,
                "roster_id": roster_id,
                "starters": starters,
            },
        )

    async def read_scoring_lineup(self, *, week: int, league_id: str, roster_id: int) -> list[str] | None:
        """Return the scoring starters for one roster, or None if that roster is absent."""
        data = await self.execute(READ_SCORING_LINEUPS, {"round": week, "league_id": league_id})
        legs = data.get("matchup_legs")
        if not isinstance(legs, list):
            raise ProviderError("Sleeper did not return scoring lineups.", provider="sleeper")
        for leg in legs:
            if isinstance(leg, dict) and str(leg.get("roster_id")) == str(roster_id):
                starters = leg.get("starters")
                if not isinstance(starters, list):
                    return None
                return [str(s) for s in starters]
        return None

    async def propose_trade(
        self,
        *,
        league_id: str,
        my_roster_id: int,
        their_roster_id: int,
        give_player_ids: list[str],
        receive_player_ids: list[str],
    ) -> dict[str, Any]:
        """Offer players to one other roster.

        Sleeper pairs each player id with a roster id. A drop's roster is the
        team that owns that player now. An add's roster is the team that receives him.
        """
        if not give_player_ids or not receive_player_ids:
            raise ProviderError("Sleeper was not given both sides of a trade.", provider="sleeper")
        data = await self.execute(
            PROPOSE_TRADE,
            {
                "league_id": league_id,
                "k_adds": [*receive_player_ids, *give_player_ids],
                "v_adds": [my_roster_id] * len(receive_player_ids) + [their_roster_id] * len(give_player_ids),
                "k_drops": [*give_player_ids, *receive_player_ids],
                "v_drops": [my_roster_id] * len(give_player_ids) + [their_roster_id] * len(receive_player_ids),
                "waiver_budget": None,
            },
        )
        tx = data.get("propose_trade")
        if not isinstance(tx, dict):
            raise ProviderError("Sleeper did not confirm the trade offer.", provider="sleeper")
        return tx

    async def add_free_agent(
        self,
        *,
        league_id: str,
        roster_id: int,
        week: int,
        player_id: str | None = None,
        drop_player_id: str | None = None,
    ) -> dict[str, Any]:
        if not player_id and not drop_player_id:
            raise ProviderError("Sleeper was not given a player to add or drop.", provider="sleeper")
        adds = [{"player_id": player_id, "roster_id": roster_id}] if player_id else []
        drops = [{"player_id": drop_player_id, "roster_id": roster_id}] if drop_player_id else []
        data = await self.execute(
            ADD_FREE_AGENT,
            {
                "league_id": league_id,
                "roster_id": roster_id,
                "leg": week,
                "adds": adds,
                "drops": drops,
            },
        )
        tx = data.get("league_create_roster_transaction")
        if not isinstance(tx, dict):
            raise ProviderError("Sleeper did not confirm the roster move.", provider="sleeper")
        return tx

    async def league_messages(self, league_id: str) -> list[dict[str, Any]]:
        """The league message board. Every manager in the league can read it."""
        return await self.thread_messages(league_id)

    async def my_dms(self) -> list[dict[str, Any]]:
        """Direct threads the signed-in account belongs to."""
        data = await self.execute(MY_DMS)
        rows = data.get("my_dms")
        if rows is None:
            return []
        if not isinstance(rows, list):
            raise ProviderError("Sleeper did not return your direct chats.", provider="sleeper")
        return [row for row in rows if isinstance(row, dict)]

    async def thread_messages(self, parent_id: str) -> list[dict[str, Any]]:
        data = await self.execute(LEAGUE_MESSAGES, {"parent_id": parent_id})
        rows = data.get("messages")
        if rows is None:
            return []
        if not isinstance(rows, list):
            raise ProviderError("Sleeper did not return that conversation.", provider="sleeper")
        return [row for row in rows if isinstance(row, dict)]

    async def create_dm(self, user_id: str) -> str:
        data = await self.execute(CREATE_DM, {"dm_type": "single", "members": [user_id]})
        created = data.get("create_dm")
        if not isinstance(created, dict) or not created.get("dm_id"):
            raise ProviderError("Sleeper did not open that chat.", provider="sleeper")
        return str(created["dm_id"])

    async def respond_trade(self, *, league_id: str, transaction_id: str, week: int, accept: bool) -> dict[str, Any]:
        query = ACCEPT_TRADE if accept else REJECT_TRADE
        data = await self.execute(
            query,
            {"leg": week, "league_id": league_id, "transaction_id": transaction_id},
        )
        key = "accept_trade" if accept else "reject_trade"
        result = data.get(key)
        if not isinstance(result, dict):
            raise ProviderError("Sleeper did not confirm the trade response.", provider="sleeper")
        return result

    async def send_message(self, parent_id: str, parent_type: str, text: str) -> None:
        await self.execute(
            CREATE_MESSAGE,
            {"parent_id": parent_id, "parent_type": parent_type, "text": text},
        )

    async def set_reserve(self, *, league_id: str, roster_id: int, reserve: list[str]) -> None:
        await self.execute(
            SET_RESERVE,
            {"league_id": league_id, "roster_id": roster_id, "reserve": reserve},
        )

    async def read_reserve(self, *, league_id: str, roster_id: int) -> list[str] | None:
        data = await self.execute(READ_ROSTERS, {"league_id": league_id})
        rosters = data.get("league_rosters")
        if not isinstance(rosters, list):
            raise ProviderError("Sleeper did not return rosters.", provider="sleeper")
        for roster in rosters:
            if isinstance(roster, dict) and str(roster.get("roster_id")) == str(roster_id):
                reserve = roster.get("reserve") or []
                if not isinstance(reserve, list):
                    return None
                return [str(player_id) for player_id in reserve if player_id]
        return None


def _error_message(errors: list) -> str:
    first = errors[0]
    if isinstance(first, dict):
        return str(first.get("message") or "Sleeper rejected the request.")
    return str(first)
