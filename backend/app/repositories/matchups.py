from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Matchup


class MatchupRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_week(self, league_id: UUID, week: int) -> list[Matchup]:
        result = await self.session.execute(
            select(Matchup).where(Matchup.league_id == league_id, Matchup.week == week)
        )
        return list(result.scalars().all())

    async def get_for_team(self, league_id: UUID, week: int, team_id: UUID) -> Matchup | None:
        result = await self.session.execute(
            select(Matchup).where(
                Matchup.league_id == league_id, Matchup.week == week, Matchup.team_id == team_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        league_id: UUID,
        week: int,
        team_id: UUID,
        opponent_team_id: UUID | None,
        external_matchup_id: str | None,
        points: float,
        projected_points: float | None,
        player_points: dict[str, float],
    ) -> Matchup:
        matchup = await self.get_for_team(league_id, week, team_id)
        if matchup is None:
            matchup = Matchup(league_id=league_id, week=week, team_id=team_id)
            self.session.add(matchup)
        matchup.opponent_team_id = opponent_team_id
        matchup.external_matchup_id = external_matchup_id
        matchup.points = points
        matchup.projected_points = projected_points
        matchup.player_points = player_points
        await self.session.flush()
        return matchup
