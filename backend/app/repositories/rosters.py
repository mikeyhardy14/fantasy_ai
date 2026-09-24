from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import FantasyTeam, RosterEntry


class RosterRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_team(self, team_id: UUID, week: int) -> list[RosterEntry]:
        result = await self.session.execute(
            select(RosterEntry)
            .where(RosterEntry.fantasy_team_id == team_id, RosterEntry.week == week)
            .options(joinedload(RosterEntry.player))
            .order_by(RosterEntry.is_starter.desc(), RosterEntry.slot_index, RosterEntry.roster_slot)
        )
        return list(result.scalars().unique().all())

    async def list_for_league(self, league_id: UUID, week: int) -> list[RosterEntry]:
        result = await self.session.execute(
            select(RosterEntry)
            .join(FantasyTeam, FantasyTeam.id == RosterEntry.fantasy_team_id)
            .where(FantasyTeam.league_id == league_id, RosterEntry.week == week)
            .options(joinedload(RosterEntry.player))
        )
        return list(result.scalars().unique().all())

    async def replace_for_team(
        self, team_id: UUID, week: int, entries: list[tuple[UUID, str, bool, int | None]]
    ) -> None:
        """Atomically replace a team's roster for a week. Idempotent."""
        await self.session.execute(
            delete(RosterEntry).where(RosterEntry.fantasy_team_id == team_id, RosterEntry.week == week)
        )
        seen: set[UUID] = set()
        for player_id, slot, is_starter, slot_index in entries:
            if player_id in seen:
                continue
            seen.add(player_id)
            self.session.add(
                RosterEntry(
                    fantasy_team_id=team_id,
                    player_id=player_id,
                    week=week,
                    roster_slot=slot,
                    is_starter=is_starter,
                    slot_index=slot_index,
                )
            )
        await self.session.flush()
