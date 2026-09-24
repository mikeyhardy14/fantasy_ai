from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction


class TransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_recent(self, league_id: UUID, limit: int = 25) -> list[Transaction]:
        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.league_id == league_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def upsert(
        self,
        *,
        league_id: UUID,
        external_transaction_id: str,
        type: str,
        status: str,
        week: int | None,
        created_at: datetime,
        details: dict,
    ) -> Transaction:
        result = await self.session.execute(
            select(Transaction).where(
                Transaction.league_id == league_id,
                Transaction.external_transaction_id == external_transaction_id,
            )
        )
        tx = result.scalar_one_or_none()
        if tx is None:
            tx = Transaction(league_id=league_id, external_transaction_id=external_transaction_id)
            self.session.add(tx)
        tx.type = type
        tx.status = status
        tx.week = week
        tx.created_at = created_at
        tx.details = details
        await self.session.flush()
        return tx
