"""Serve league pages from the session DB; refresh Sleeper only when stale.

Imported league rows are the session database. Page loads read them first.
A durable TTL on ``last_synced_at`` skips Sleeper until the session ages out.
Parallel requests for the same league share one pull when a refresh does run.
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import ProviderNotImplemented
from app.core.logging import get_logger
from app.domain.enums import Provider
from app.models import League
from app.providers.registry import ProviderRegistry
from app.services.sync_service import SyncService

log = get_logger(__name__)

_locks: dict[str, asyncio.Lock] = {}


def session_is_fresh(league: League, *, ttl_seconds: float, now: datetime | None = None) -> bool:
    """True when the DB session is new enough to skip Sleeper."""
    if league.last_synced_at is None:
        return False
    synced = league.last_synced_at
    if synced.tzinfo is None:
        synced = synced.replace(tzinfo=UTC)
    age = ((now or datetime.now(UTC)) - synced).total_seconds()
    return age < ttl_seconds


async def ensure_live(
    league: League,
    session: AsyncSession,
    providers: ProviderRegistry,
    *,
    settings: Settings | None = None,
    force: bool = False,
) -> None:
    """Use the session DB when fresh; otherwise pull a light Sleeper refresh."""
    if league.provider != Provider.SLEEPER.value:
        return
    cfg = settings or get_settings()
    ttl = float(cfg.sleeper_live_ttl_seconds)
    if not force and session_is_fresh(league, ttl_seconds=ttl):
        return

    key = str(league.id)
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        await session.refresh(league)
        if not force and session_is_fresh(league, ttl_seconds=ttl):
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
