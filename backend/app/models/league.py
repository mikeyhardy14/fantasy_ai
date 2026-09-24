import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import SyncStatus

if TYPE_CHECKING:
    from app.models.fantasy_account import FantasyAccount
    from app.models.matchup import Matchup
    from app.models.team import FantasyTeam
    from app.models.transaction import Transaction


class League(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leagues"
    __table_args__ = (
        UniqueConstraint("fantasy_account_id", "external_league_id", name="uq_league_identity"),
    )

    fantasy_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fantasy_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_league_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    team_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_week: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str | None] = mapped_column(String(32))
    avatar: Mapped[str | None] = mapped_column(String(512))

    scoring_settings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # {"roster_positions": [...], "max_roster_size": n, "taxi_slots": n, "reserve_slots": n}
    roster_settings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # waiver type, FAAB budget, playoff config, etc.
    league_settings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_status: Mapped[str] = mapped_column(String(16), nullable=False, default=SyncStatus.IDLE)
    sync_error: Mapped[str | None] = mapped_column(Text)

    fantasy_account: Mapped["FantasyAccount"] = relationship(back_populates="leagues")
    teams: Mapped[list["FantasyTeam"]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )
    matchups: Mapped[list["Matchup"]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )

    @property
    def roster_positions(self) -> list[str]:
        return list(self.roster_settings.get("roster_positions") or [])
