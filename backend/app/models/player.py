import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass


class Player(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Internal, provider-neutral player identity.

    Provider IDs live in PlayerExternalId so one player can be mapped from
    Sleeper, Yahoo, ESPN and NFL simultaneously.
    """

    __tablename__ = "players"

    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    first_name: Mapped[str | None] = mapped_column(String(80))
    last_name: Mapped[str | None] = mapped_column(String(80), index=True)
    position: Mapped[str | None] = mapped_column(String(8), index=True)
    fantasy_positions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    nfl_team: Mapped[str | None] = mapped_column(String(8), index=True)
    status: Mapped[str | None] = mapped_column(String(32))  # Active, Inactive, ...
    injury_status: Mapped[str | None] = mapped_column(String(32))  # Questionable, Out, IR ...
    injury_body_part: Mapped[str | None] = mapped_column(String(64))
    age: Mapped[int | None] = mapped_column(Integer)
    years_exp: Mapped[int | None] = mapped_column(Integer)
    number: Mapped[int | None] = mapped_column(Integer)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    external_ids: Mapped[list["PlayerExternalId"]] = relationship(
        back_populates="player", cascade="all, delete-orphan", lazy="selectin"
    )

    def external_id_for(self, provider: str) -> str | None:
        for ext in self.external_ids:
            if ext.provider == provider:
                return ext.external_id
        return None


class PlayerExternalId(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "player_external_ids"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_player_external"),)

    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)

    player: Mapped["Player"] = relationship(back_populates="external_ids")
