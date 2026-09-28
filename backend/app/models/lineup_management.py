import uuid

from sqlalchemy import Boolean, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LineupManagement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Whether AI Management may edit this league's current lineup."""

    __tablename__ = "lineup_management"
    __table_args__ = (UniqueConstraint("user_id", "league_id", name="uq_lineup_management_league"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    league_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
