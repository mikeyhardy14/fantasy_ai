import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.league import League
    from app.models.user import User


class FantasyAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A link between an app user and an identity on a fantasy platform."""

    __tablename__ = "fantasy_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "external_user_id", name="uq_account_identity"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128))
    avatar: Mapped[str | None] = mapped_column(String(512))
    # Fernet ciphertext. For Sleeper this is the account JWT used for lineup writes.
    encrypted_credentials: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="fantasy_accounts")
    leagues: Mapped[list["League"]] = relationship(
        back_populates="fantasy_account", cascade="all, delete-orphan"
    )
