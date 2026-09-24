from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import FantasyAccount, League


class LeagueRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_user(self, user_id: UUID) -> list[League]:
        result = await self.session.execute(
            select(League)
            .join(League.fantasy_account)
            .where(FantasyAccount.user_id == user_id)
            .options(joinedload(League.fantasy_account))
            .order_by(League.season.desc(), League.name)
        )
        return list(result.scalars().unique().all())

    async def get_owned(self, user_id: UUID, league_id: UUID) -> League | None:
        """Return the league only if it belongs to the given user."""
        result = await self.session.execute(
            select(League)
            .join(League.fantasy_account)
            .where(League.id == league_id, FantasyAccount.user_id == user_id)
            .options(joinedload(League.fantasy_account))
        )
        return result.scalar_one_or_none()

    async def get_by_identity(self, account_id: UUID, external_league_id: str) -> League | None:
        result = await self.session.execute(
            select(League)
            .where(
                League.fantasy_account_id == account_id,
                League.external_league_id == external_league_id,
            )
            .options(joinedload(League.fantasy_account))
        )
        return result.scalar_one_or_none()

    async def get(self, league_id: UUID) -> League | None:
        result = await self.session.execute(
            select(League).where(League.id == league_id).options(joinedload(League.fantasy_account))
        )
        return result.scalar_one_or_none()

    def add(self, league: League) -> League:
        self.session.add(league)
        return league
