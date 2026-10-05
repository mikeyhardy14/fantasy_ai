"""In-memory sliding-window limits for one API process."""

import time
from collections import defaultdict, deque

from app.core.errors import AppError


class RateLimited(AppError):
    """Too many requests. Try again shortly."""

    status_code = 429
    code = "rate_limited"


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str, *, limit: int, window_seconds: float) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            raise RateLimited("Too many requests. Wait a minute and try again.")
        hits.append(now)
        if len(self._hits) > 10_000:
            self._prune(now, window_seconds)

    def _prune(self, now: float, window_seconds: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or now - v[-1] > window_seconds]:
            del self._hits[key]
