"""Which NFL week the board should show.

Sleeper's league `leg` often stays on the week that just finished until
Wednesday. Once that slate is final, Tuesday in America/New_York starts
the next week.
"""

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def _eastern(now: datetime | None) -> datetime:
    stamp = now or datetime.now(UTC)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    try:
        return stamp.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        return stamp.astimezone(timezone(timedelta(hours=-4)))


def board_week(provider_week: int, *, slate_final: bool, now: datetime | None = None) -> int:
    week = min(18, max(1, int(provider_week)))
    if not slate_final or week >= 18:
        return week
    if _eastern(now).weekday() in {0, 6}:
        return week
    return week + 1
