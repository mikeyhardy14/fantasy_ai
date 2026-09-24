"""Persists a provider snapshot into the normalized database.

Every write is an upsert on a natural key so running the sync twice yields the
same rows (idempotent). Roster entries for (team, week) are replaced as a set.
"""

from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.enums import SyncStatus
from app.domain.provider_models import ImportedLeagueSnapshot, PlayerData
from app.models import League, Player
from app.providers.base import FantasyProvider
from app.repositories import (
    MatchupRepository,
    PlayerRepository,
    RosterRepository,
    TeamRepository,
    TransactionRepository,
)

log = get_logger(__name__)


class SyncService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.teams = TeamRepository(session)
        self.players = PlayerRepository(session)
        self.rosters = RosterRepository(session)
        self.matchups = MatchupRepository(session)
        self.transactions = TransactionRepository(session)

    async def sync_league(self, league: League, provider: FantasyProvider) -> League:
        """Fetch a fresh snapshot from the provider and persist it."""
        league.sync_status = SyncStatus.SYNCING
        league.sync_error = None
        await self.session.commit()
        try:
            snapshot = await provider.fetch_league_snapshot(league.external_league_id)
            await self.apply_snapshot(league, snapshot)
            league.sync_status = SyncStatus.SUCCESS
            league.sync_error = None
            league.last_synced_at = datetime.now(UTC)
            league.fantasy_account.last_synced_at = league.last_synced_at
            await self.session.commit()
            log.info("sync.success", league_id=str(league.id), provider=league.provider)
        except Exception as exc:
            await self.session.rollback()
            league.sync_status = SyncStatus.ERROR
            league.sync_error = str(exc)[:1000]
            await self.session.commit()
            log.warning("sync.failed", league_id=str(league.id), error=str(exc))
            raise
        return league

    async def apply_snapshot(self, league: League, snapshot: ImportedLeagueSnapshot) -> None:
        provider = snapshot.provider.value
        details = snapshot.league

        # -- league -------------------------------------------------------------
        league.name = details.name
        league.season = details.season
        league.team_count = details.team_count or len(snapshot.teams)
        league.current_week = details.current_week
        league.status = details.status
        league.avatar = details.avatar
        league.scoring_settings = details.scoring_settings
        league.roster_settings = details.roster_settings
        league.league_settings = details.league_settings

        # -- teams --------------------------------------------------------------
        teams_by_ext = await self.teams.upsert_many(league.id, snapshot.teams)

        # -- players ------------------------------------------------------------
        referenced: set[str] = set()
        for roster in snapshot.rosters:
            referenced.update(e.external_player_id for e in roster.entries)
        for m in snapshot.matchups:
            referenced.update(m.player_points.keys())
        for t in snapshot.transactions:
            referenced.update(a["external_player_id"] for a in t.adds)
            referenced.update(d["external_player_id"] for d in t.drops)

        to_persist: dict[str, PlayerData] = {}
        for ext_id, pdata in snapshot.players.items():
            if ext_id in referenced or pdata.is_fantasy_relevant:
                to_persist[ext_id] = pdata
        for ext_id in referenced - set(to_persist):
            # Referenced but missing from the catalogue: keep a placeholder so FK holds.
            to_persist[ext_id] = PlayerData(external_player_id=ext_id, name=f"Unknown player {ext_id}")
        players_by_ext: dict[str, Player] = await self.players.upsert_many(provider, to_persist.values())

        # -- rosters (replace per team/week) --------------------------------------
        week = league.current_week
        for roster in snapshot.rosters:
            team = teams_by_ext.get(roster.external_team_id)
            if team is None:
                continue
            entries = []
            for e in roster.entries:
                player = players_by_ext.get(e.external_player_id)
                if player is None:
                    continue
                entries.append((player.id, e.roster_slot, e.is_starter, e.slot_index))
            await self.rosters.replace_for_team(team.id, week, entries)

        # -- matchups -----------------------------------------------------------
        by_week_matchup: dict[tuple[int, str | None], list] = defaultdict(list)
        for m in snapshot.matchups:
            by_week_matchup[(m.week, m.external_matchup_id)].append(m)
        for (mweek, ext_matchup_id), sides in by_week_matchup.items():
            for side in sides:
                team = teams_by_ext.get(side.external_team_id)
                if team is None:
                    continue
                opponent = None
                if ext_matchup_id is not None:
                    for other in sides:
                        if other is not side:
                            opponent = teams_by_ext.get(other.external_team_id)
                            break
                player_points = {
                    str(players_by_ext[pid].id): pts
                    for pid, pts in side.player_points.items()
                    if pid in players_by_ext
                }
                await self.matchups.upsert(
                    league_id=league.id,
                    week=mweek,
                    team_id=team.id,
                    opponent_team_id=opponent.id if opponent else None,
                    external_matchup_id=ext_matchup_id,
                    points=side.points,
                    projected_points=side.projected_points,
                    player_points=player_points,
                )

        # -- transactions -------------------------------------------------------
        for t in snapshot.transactions:
            def _map(items: list[dict[str, str]]) -> list[dict]:
                out = []
                for item in items:
                    player = players_by_ext.get(item["external_player_id"])
                    team = teams_by_ext.get(item.get("external_team_id", ""))
                    out.append(
                        {
                            "player_id": str(player.id) if player else None,
                            "player_name": player.name if player else None,
                            "position": player.position if player else None,
                            "team_id": str(team.id) if team else None,
                            "team_name": team.name if team else None,
                        }
                    )
                return out

            await self.transactions.upsert(
                league_id=league.id,
                external_transaction_id=t.external_transaction_id,
                type=t.type,
                status=t.status,
                week=t.week,
                created_at=t.created_at,
                details={
                    "adds": _map(t.adds),
                    "drops": _map(t.drops),
                    "team_ids": [
                        str(teams_by_ext[e].id) for e in t.external_team_ids if e in teams_by_ext
                    ],
                    "team_names": [
                        teams_by_ext[e].name for e in t.external_team_ids if e in teams_by_ext
                    ],
                    "faab_bid": t.faab_bid,
                    **t.metadata,
                },
            )
        await self.session.flush()
