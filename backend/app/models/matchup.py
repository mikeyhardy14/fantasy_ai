import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.league import League
    from app.models.team import FantasyTeam


class Matchup(UUIDPrimaryKeyMixin, Base):
    """One team's side of a weekly matchup. opponent_team_id is None on a bye."""

    __tablename__ = "matchups"
    __table_args__ = (UniqueConstraint("league_id", "week", "team_id", name="uq_matchup_team"),)

    league_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    week: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    external_matchup_id: Mapped[str | None] = mapped_column(String(64))
    team_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fantasy_teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opponent_team_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fantasy_teams.id", ondelete="SET NULL")
    )
    points: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    projected_points: Mapped[float | None] = mapped_column(Float)
    # {internal_player_id: points}
    player_points: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    league: Mapped["League"] = relationship(back_populates="matchups")
    team: Mapped["FantasyTeam"] = relationship(foreign_keys=[team_id])
    opponent: Mapped["FantasyTeam | None"] = relationship(foreign_keys=[opponent_team_id])
