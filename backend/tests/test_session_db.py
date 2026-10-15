"""Session DB freshness: serve synced leagues without re-hitting Sleeper."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.services.live_league import session_is_fresh


def test_session_is_fresh_when_recently_synced():
    league = SimpleNamespace(last_synced_at=datetime.now(UTC) - timedelta(seconds=30))
    assert session_is_fresh(league, ttl_seconds=180)  # type: ignore[arg-type]
    assert not session_is_fresh(league, ttl_seconds=10)  # type: ignore[arg-type]


def test_session_is_stale_without_sync_timestamp():
    league = SimpleNamespace(last_synced_at=None)
    assert not session_is_fresh(league, ttl_seconds=180)  # type: ignore[arg-type]
