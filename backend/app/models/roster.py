import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.player import Player
    from app.models.team import FantasyTeam


class RosterEntry(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "roster_entries"
    __table_args__ = (
        UniqueConstraint("fantasy_team_id", "player_id", "week", name="uq_roster_entry"),
    )

    fantasy_team_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fantasy_teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    roster_slot: Mapped[str] = mapped_column(String(16), nullable=False)  # QB, FLEX, BN, IR...
    slot_index: Mapped[int | None] = mapped_column(Integer)  # order within lineup
    is_starter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    team: Mapped["FantasyTeam"] = relationship(back_populates="roster_entries")
    player: Mapped["Player"] = relationship(lazy="joined")
