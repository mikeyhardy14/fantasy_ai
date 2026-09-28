"""AI Management: sub starters who cannot play, and activate IR players who can.

Questionable starters stay put. Projection upgrades of a healthy starter are not made.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.logging import get_logger
from app.db.session import Database
from app.domain.enums import Provider
from app.intelligence.lineup import _proj, injury_severity, is_eligible, is_unavailable
from app.models import League, LineupManagement, User
from app.repositories import LeagueRepository
from app.schemas.league import (
    LineupManagementOut,
    LineupManagementUpdate,
    RosterMoveRequest,
    RosterSlotOut,
    TeamOut,
)
from app.services.league_context import LeagueContextService
from app.services.sleeper_writes import build_sleeper_write_service

log = get_logger(__name__)

_lock = asyncio.Lock()
ApplyMove = Callable[[League, "LineupMove"], Awaitable[str]]


@dataclass
class LineupMove:
    player_id: UUID
    player_name: str
    destination: Literal["starter", "bench"]
    slot_index: int | None
    summary: str


def plan_management(team: TeamOut) -> list[LineupMove]:
    """Moves for one roster. Starters who cannot play are replaced first, then healthy IR players come to the bench."""
    bench = [row for row in team.bench if row.player]
    reserve = [row for row in team.reserve if row.player]
    taken: set[str] = set()
    moves: list[LineupMove] = []

    def candidates(slot_name: str) -> list[RosterSlotOut]:
        pool = [
            row
            for row in [*bench, *reserve]
            if row.player
            and str(row.player.id) not in taken
            and not is_unavailable(row)
            and is_eligible(row.player, slot_name)
        ]
        pool.sort(key=lambda row: (_proj(row) is None, -(_proj(row) or 0.0), injury_severity(row.player)))  # type: ignore[arg-type]
        return pool

    for starter in team.starters:
        if starter.slot_index is None:
            continue
        if starter.player is not None and not is_unavailable(starter):
            continue
        pool = candidates(starter.slot)
        if not pool:
            continue
        pick = pool[0]
        assert pick.player is not None
        taken.add(str(pick.player.id))
        replaced = starter.player.name if starter.player else "an empty slot"
        reason = "can play" if starter.player is None else _why(starter)
        moves.append(
            LineupMove(
                player_id=pick.player.id,
                player_name=pick.player.name,
                destination="starter",
                slot_index=starter.slot_index,
                summary=f"Start {pick.player.name} at {starter.slot} for {replaced}, who {reason}.",
            )
        )

    for row in reserve:
        if row.player is None or str(row.player.id) in taken or is_unavailable(row):
            continue
        taken.add(str(row.player.id))
        moves.append(
            LineupMove(
                player_id=row.player.id,
                player_name=row.player.name,
                destination="bench",
                slot_index=None,
                summary=f"Activate {row.player.name} from IR.",
            )
        )
    return moves


def _why(slot: RosterSlotOut) -> str:
    if "BYE" in slot.flags:
        return "is on bye"
    status = (slot.player.injury_status if slot.player else None) or "cannot play"
    return f"is {status}"


def _available(league: League) -> bool:
    return league.provider == Provider.SLEEPER and bool(league.fantasy_account.encrypted_credentials)


async def _load(session: AsyncSession, user_id, league_id) -> LineupManagement | None:
    result = await session.execute(
        select(LineupManagement).where(
            LineupManagement.user_id == user_id, LineupManagement.league_id == league_id
        )
    )
    return result.scalar_one_or_none()


def _out(row: LineupManagement | None, league: League) -> LineupManagementOut:
    return LineupManagementOut(enabled=bool(row and row.enabled), available=_available(league))


async def get_lineup_management(session: AsyncSession, user: User, league: League) -> LineupManagementOut:
    return _out(await _load(session, user.id, league.id), league)


async def save_lineup_management(
    session: AsyncSession, user: User, league: League, body: LineupManagementUpdate
) -> LineupManagementOut:
    from app.core.errors import ValidationFailed

    if league.provider != Provider.SLEEPER:
        raise ValidationFailed("AI Management edits Sleeper lineups.")
    if not league.fantasy_account.encrypted_credentials:
        raise ValidationFailed("Save your Sleeper token in Settings to turn on AI Management.")
    row = await _load(session, user.id, league.id)
    if row is None:
        row = LineupManagement(user_id=user.id, league_id=league.id, enabled=body.enabled)
        session.add(row)
    else:
        row.enabled = body.enabled
    await session.commit()
    return _out(row, league)


async def ensure_lineup_management_table(db: Database) -> None:
    def _ensure(sync_conn) -> None:
        LineupManagement.__table__.create(sync_conn, checkfirst=True)

    async with db.engine.begin() as conn:
        await conn.run_sync(_ensure)


async def sweep_lineup_management(state, apply: ApplyMove | None = None) -> list[str]:
    """Apply at most the planned moves for each league that has AI Management on."""
    async with _lock:
        done: list[str] = []
        async with state.db.session_factory() as session:
            result = await session.execute(select(LineupManagement).where(LineupManagement.enabled.is_(True)))
            for row in result.scalars().all():
                try:
                    done.extend(await _sweep_league(state, session, row, apply))
                except Exception:
                    log.exception("lineup_management.league_failed", league_id=str(row.league_id))
                    await session.rollback()
        return done


async def _sweep_league(state, session: AsyncSession, row: LineupManagement, apply: ApplyMove | None) -> list[str]:
    league = await LeagueRepository(session).get_owned(row.user_id, row.league_id)
    if league is None or not _available(league):
        return []
    context = LeagueContextService(
        session, state.nfl_data, state.weekly_stats, state.props, state.sleeper_projections
    )
    team = await context.user_team_out(league, league.current_week)
    moves = plan_management(team)
    if not moves:
        return []
    writes = build_sleeper_write_service(
        session, context, state.providers, state.cipher, state.settings.sleeper_graphql_url
    )
    done: list[str] = []
    for move in moves:
        try:
            if apply is None:
                result = await writes.move_player(
                    league,
                    RosterMoveRequest(
                        week=league.current_week,
                        player_id=move.player_id,
                        destination=move.destination,
                        slot_index=move.slot_index,
                    ),
                )
                message = result.message
            else:
                message = await apply(league, move)
        except AppError as exc:
            log.warning("lineup_management.move_failed", league_id=str(league.id), error=exc.message)
            return done
        done.append(move.summary)
        log.info("lineup_management.moved", league_id=str(league.id), summary=move.summary, result=message)
    return done
