import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


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


class AutoReplySetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Whether Auto AI fantasy may answer direct messages in one league."""

    __tablename__ = "auto_reply_settings"
    __table_args__ = (UniqueConstraint("user_id", "league_id", name="uq_auto_reply_league"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    league_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    targets: Mapped[list["AutoReplyTarget"]] = relationship(
        back_populates="setting", cascade="all, delete-orphan", lazy="selectin"
    )


class AutoReplyTarget(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One manager this user wants answered, and the last message already handled."""

    __tablename__ = "auto_reply_targets"
    __table_args__ = (UniqueConstraint("setting_id", "sleeper_user_id", name="uq_auto_reply_person"),)

    setting_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("auto_reply_settings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sleeper_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_message_id: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    setting: Mapped[AutoReplySetting] = relationship(back_populates="targets")
