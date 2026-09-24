from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.provider_models import PlayerData
from app.models import FantasyTeam, Player, PlayerExternalId, RosterEntry


class PlayerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, player_id: UUID) -> Player | None:
        return await self.session.get(Player, player_id)

    async def get_many(self, player_ids: Iterable[UUID]) -> dict[UUID, Player]:
        ids = list(player_ids)
        if not ids:
            return {}
        result = await self.session.execute(select(Player).where(Player.id.in_(ids)))
        return {p.id: p for p in result.scalars().unique().all()}

    async def map_external_ids(self, provider: str, external_ids: Iterable[str]) -> dict[str, Player]:
        ids = list({str(e) for e in external_ids})
        out: dict[str, Player] = {}
        for i in range(0, len(ids), 500):
            chunk = ids[i : i + 500]
            result = await self.session.execute(
                select(PlayerExternalId.external_id, Player)
                .join(Player, Player.id == PlayerExternalId.player_id)
                .where(PlayerExternalId.provider == provider, PlayerExternalId.external_id.in_(chunk))
            )
            for external_id, player in result.unique().all():
                out[external_id] = player
        return out

    async def upsert_many(self, provider: str, players: Iterable[PlayerData]) -> dict[str, Player]:
        """Idempotently create/update players by (provider, external_id)."""
        items = list(players)
        existing = await self.map_external_ids(provider, (p.external_player_id for p in items))
        out: dict[str, Player] = {}
        for data in items:
            player = existing.get(data.external_player_id)
            if player is None:
                player = Player(name=data.name, fantasy_positions=[], extra={})
                player.external_ids.append(
                    PlayerExternalId(provider=provider, external_id=data.external_player_id)
                )
                self.session.add(player)
            player.name = data.name
            player.first_name = data.first_name
            player.last_name = data.last_name
            player.position = data.position
            player.fantasy_positions = data.fantasy_positions
            player.nfl_team = data.nfl_team
            player.status = data.status
            player.injury_status = data.injury_status
            player.injury_body_part = data.injury_body_part
            player.age = data.age
            player.years_exp = data.years_exp
            player.number = data.number
            player.extra = data.extra
            out[data.external_player_id] = player
        await self.session.flush()
        return out

    async def add_external_id(self, player: Player, provider: str, external_id: str) -> None:
        if player.external_id_for(provider) == external_id:
            return
        player.external_ids.append(PlayerExternalId(provider=provider, external_id=external_id))
        await self.session.flush()

    async def rostered_player_ids(self, league_id: UUID, week: int) -> set[UUID]:
        result = await self.session.execute(
            select(RosterEntry.player_id)
            .join(FantasyTeam, FantasyTeam.id == RosterEntry.fantasy_team_id)
            .where(FantasyTeam.league_id == league_id, RosterEntry.week == week)
        )
        return set(result.scalars().all())

    async def search(
        self,
        *,
        provider: str,
        exclude_ids: set[UUID] | None = None,
        position: str | None = None,
        query: str | None = None,
        nfl_team: str | None = None,
        limit: int = 50,
        only_active: bool = True,
    ) -> list[Player]:
        stmt = (
            select(Player)
            .join(PlayerExternalId, PlayerExternalId.player_id == Player.id)
            .where(PlayerExternalId.provider == provider)
        )
        if only_active:
            stmt = stmt.where(Player.nfl_team.is_not(None))
        if exclude_ids:
            stmt = stmt.where(Player.id.not_in(list(exclude_ids)))
        if position:
            stmt = stmt.where(Player.position == position.upper())
        if nfl_team:
            stmt = stmt.where(Player.nfl_team == nfl_team.upper())
        if query:
            like = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(func.lower(Player.name).like(like), func.lower(Player.last_name).like(like))
            )
        stmt = stmt.order_by(Player.position, Player.last_name).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_active(self, provider: str, positions: Iterable[str]) -> list[Player]:
        pos = [item.upper() for item in positions]
        if not pos:
            return []
        stmt = (
            select(Player)
            .join(PlayerExternalId, PlayerExternalId.player_id == Player.id)
            .where(
                PlayerExternalId.provider == provider,
                Player.nfl_team.is_not(None),
                Player.position.in_(pos),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())
