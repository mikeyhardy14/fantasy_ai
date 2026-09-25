"""Refresh a Sleeper league from the provider when a page reads it.

Parallel requests for the same league share one pull. A short window keeps a
dashboard full of requests from fetching Sleeper once per endpoint.
"""

import asyncio
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProviderNotImplemented
from app.core.logging import get_logger
from app.domain.enums import Provider
from app.models import League
from app.providers.registry import ProviderRegistry
from app.services.sync_service import SyncService

log = get_logger(__name__)

_FRESH_SECONDS = 10.0
_fresh: dict[str, float] = {}
_locks: dict[str, asyncio.Lock] = {}


async def ensure_live(league: League, session: AsyncSession, providers: ProviderRegistry) -> None:
    if league.provider != Provider.SLEEPER.value:
        return
    key = str(league.id)
    if time.monotonic() - _fresh.get(key, 0) < _FRESH_SECONDS:
        return
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        if time.monotonic() - _fresh.get(key, 0) < _FRESH_SECONDS:
            return
        try:
            adapter = providers.get(league.provider)
        except ProviderNotImplemented:
            return
        try:
            await SyncService(session).refresh_live(league, adapter)
        except Exception as exc:  # noqa: BLE001 - serve the last good league if Sleeper blips
            await session.rollback()
            await session.refresh(league)
            log.warning("league.live_refresh_failed", league_id=key, error=str(exc))
            return
        _fresh[key] = time.monotonic()
