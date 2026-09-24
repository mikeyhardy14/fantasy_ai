from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.provider_models import ProviderUser
from app.models import FantasyAccount


class FantasyAccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_user(self, user_id: UUID) -> list[FantasyAccount]:
        result = await self.session.execute(
            select(FantasyAccount)
            .where(FantasyAccount.user_id == user_id)
            .order_by(FantasyAccount.created_at)
        )
        return list(result.scalars().all())

    async def get_for_user(self, user_id: UUID, account_id: UUID) -> FantasyAccount | None:
        result = await self.session.execute(
            select(FantasyAccount).where(
                FantasyAccount.id == account_id, FantasyAccount.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_provider(self, user_id: UUID, provider: str) -> list[FantasyAccount]:
        result = await self.session.execute(
            select(FantasyAccount).where(
                FantasyAccount.user_id == user_id, FantasyAccount.provider == provider
            )
        )
        return list(result.scalars().all())

    async def upsert(self, user_id: UUID, provider: str, identity: ProviderUser) -> FantasyAccount:
        result = await self.session.execute(
            select(FantasyAccount).where(
                FantasyAccount.user_id == user_id,
                FantasyAccount.provider == provider,
                FantasyAccount.external_user_id == identity.external_user_id,
            )
        )
        account = result.scalar_one_or_none()
        if account is None:
            account = FantasyAccount(
                user_id=user_id, provider=provider, external_user_id=identity.external_user_id
            )
            self.session.add(account)
        account.username = identity.username
        account.display_name = identity.display_name
        account.avatar = identity.avatar
        await self.session.flush()
        return account
