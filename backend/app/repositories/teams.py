from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.provider_models import TeamData
from app.models import FantasyTeam


class TeamRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_league(self, league_id: UUID) -> list[FantasyTeam]:
        result = await self.session.execute(
            select(FantasyTeam).where(FantasyTeam.league_id == league_id).order_by(FantasyTeam.name)
        )
        return list(result.scalars().all())

    async def get(self, league_id: UUID, team_id: UUID) -> FantasyTeam | None:
        result = await self.session.execute(
            select(FantasyTeam).where(FantasyTeam.league_id == league_id, FantasyTeam.id == team_id)
        )
        return result.scalar_one_or_none()

    async def get_by_owner(self, league_id: UUID, owner_external_id: str) -> FantasyTeam | None:
        result = await self.session.execute(
            select(FantasyTeam).where(
                FantasyTeam.league_id == league_id,
                FantasyTeam.owner_external_id == owner_external_id,
            )
        )
        return result.scalars().first()

    async def upsert_many(self, league_id: UUID, teams: list[TeamData]) -> dict[str, FantasyTeam]:
        existing = {t.external_team_id: t for t in await self.list_for_league(league_id)}
        out: dict[str, FantasyTeam] = {}
        for data in teams:
            team = existing.get(data.external_team_id)
            if team is None:
                team = FantasyTeam(league_id=league_id, external_team_id=data.external_team_id)
                self.session.add(team)
            team.owner_external_id = data.owner_external_id
            team.owner_name = data.owner_name
            team.name = data.name
            team.avatar = data.avatar
            team.wins = data.wins
            team.losses = data.losses
            team.ties = data.ties
            team.points_for = data.points_for
            team.points_against = data.points_against
            team.faab_remaining = data.faab_remaining
            team.waiver_position = data.waiver_position
            team.settings = data.settings
            out[data.external_team_id] = team
        await self.session.flush()
        return out
