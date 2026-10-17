"""Refresh a Sleeper league from the provider when a page reads it.

Parallel requests for the same league share one pull. When the league already
has saved data, the request returns immediately and the refresh runs in the
background so page loads are not blocked on Sleeper.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.errors import ProviderNotImplemented
from app.core.logging import get_logger
from app.domain.enums import Provider
from app.models import League
from app.providers.registry import ProviderRegistry
from app.services.sync_service import SyncService

if TYPE_CHECKING:
    from app.db.session import Database
    from app.nfl_data.injuries import EspnInjuryClient

log = get_logger(__name__)

_FRESH_SECONDS = 10.0
_fresh: dict[str, float] = {}
_locks: dict[str, asyncio.Lock] = {}
_background: dict[str, asyncio.Task] = {}


async def ensure_live(
    league: League,
    session: AsyncSession,
    providers: ProviderRegistry,
    *,
    db: Database | None = None,
    wait: bool = False,
    injuries: EspnInjuryClient | None = None,
) -> None:
    """Refresh the league from Sleeper.

    ``wait=True`` is for writes: they build what they send to Sleeper from the
    saved roster, so they wait for the refresh (or one already in flight).
    """
    if league.provider != Provider.SLEEPER.value:
        return
    key = str(league.id)
    if time.monotonic() - _fresh.get(key, 0) < _FRESH_SECONDS:
        return

    # Already imported once: serve the DB copy and refresh Sleeper off the request path.
    if league.last_synced_at is not None and db is not None and not wait:
        _schedule_background(league.id, providers, db, injuries)
        return

    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        if time.monotonic() - _fresh.get(key, 0) < _FRESH_SECONDS:
            # A background refresh finished while this request waited on the lock.
            await session.refresh(league)
            return
        # Prefer a dedicated session so list_leagues can refresh many leagues in parallel.
        if db is not None:
            async with db.session_factory() as own_session:
                owned = await _load_league(own_session, league.id)
                if owned is None:
                    return
                await _refresh_blocking(owned, own_session, providers, injuries)
            await session.refresh(league)
        else:
            await _refresh_blocking(league, session, providers, injuries)
        _fresh[key] = time.monotonic()


async def drain_background() -> None:
    """Wait for in-flight background refreshes (tests)."""
    pending = [task for task in list(_background.values()) if not task.done()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


async def cancel_background() -> None:
    """Stop in-flight background refreshes before the DB pool and HTTP client close."""
    pending = [task for task in list(_background.values()) if not task.done()]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


def mark_fresh(league_id: UUID | str) -> None:
    """Skip Sleeper refresh for this league's freshness window (tests)."""
    _fresh[str(league_id)] = time.monotonic()


async def _load_league(session: AsyncSession, league_id: UUID) -> League | None:
    result = await session.execute(
        select(League).where(League.id == league_id).options(joinedload(League.fantasy_account))
    )
    return result.unique().scalar_one_or_none()


def _schedule_background(
    league_id: UUID, providers: ProviderRegistry, db: Database, injuries: EspnInjuryClient | None = None
) -> None:
    key = str(league_id)
    existing = _background.get(key)
    if existing is not None and not existing.done():
        return

    async def _run() -> None:
        lock = _locks.setdefault(key, asyncio.Lock())
        async with lock:
            if time.monotonic() - _fresh.get(key, 0) < _FRESH_SECONDS:
                return
            try:
                async with db.session_factory() as bg_session:
                    league = await _load_league(bg_session, league_id)
                    if league is None:
                        return
                    await _refresh_blocking(league, bg_session, providers, injuries)
                _fresh[key] = time.monotonic()
            except Exception as exc:  # noqa: BLE001 - never fail the user request path
                log.warning("league.live_refresh_failed", league_id=key, error=str(exc))
            finally:
                _background.pop(key, None)

    _background[key] = asyncio.create_task(_run())


async def _refresh_blocking(
    league: League,
    session: AsyncSession,
    providers: ProviderRegistry,
    injuries: EspnInjuryClient | None = None,
) -> None:
    try:
        adapter = providers.get(league.provider)
    except ProviderNotImplemented:
        return
    try:
        await SyncService(session, injuries).refresh_live(league, adapter)
    except Exception as exc:  # noqa: BLE001 - serve the last good league if Sleeper blips
        await session.rollback()
        await session.refresh(league)
        log.warning("league.live_refresh_failed", league_id=str(league.id), error=str(exc))
