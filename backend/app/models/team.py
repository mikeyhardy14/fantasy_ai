import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.league import League
    from app.models.roster import RosterEntry


class FantasyTeam(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fantasy_teams"
    __table_args__ = (
        UniqueConstraint("league_id", "external_team_id", name="uq_team_identity"),
    )

    league_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_team_id: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_external_id: Mapped[str | None] = mapped_column(String(128), index=True)
    owner_name: Mapped[str | None] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(512))
    wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ties: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    points_for: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    points_against: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    faab_remaining: Mapped[int | None] = mapped_column(Integer)
    waiver_position: Mapped[int | None] = mapped_column(Integer)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    league: Mapped["League"] = relationship(back_populates="teams")
    roster_entries: Mapped[list["RosterEntry"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )

    @property
    def record(self) -> str:
        base = f"{self.wins}-{self.losses}"
        return f"{base}-{self.ties}" if self.ties else base
