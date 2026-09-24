import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.league import League


class Transaction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("league_id", "external_transaction_id", name="uq_transaction_identity"),
    )

    league_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_transaction_id: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    week: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Normalized detail: {"adds": [{"player_id":..., "team_id":...}], "drops": [...],
    #                     "faab": n, "team_ids": [...], "notes": ...}
    details: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    league: Mapped["League"] = relationship(back_populates="transactions")
