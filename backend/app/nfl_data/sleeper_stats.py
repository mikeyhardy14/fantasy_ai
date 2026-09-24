"""Recent game lines from Sleeper's public weekly stats.

Each week is cached on disk. A week with no stat line for the player is skipped.
Fantasy points use the league's scoring settings when the stat keys overlap.
Otherwise the matching Sleeper column (PPR, half PPR, or standard) is shown and labeled.
"""

import asyncio
import json
import time
from pathlib import Path

import httpx
from pydantic import BaseModel

from app.core.logging import get_logger

log = get_logger(__name__)

COUNTING: tuple[tuple[str, str], ...] = (
    ("pass_yd", "pass yds"),
    ("pass_td", "pass TD"),
    ("pass_int", "INT"),
    ("rush_yd", "rush yds"),
    ("rush_td", "rush TD"),
    ("rec", "rec"),
    ("rec_yd", "rec yds"),
    ("rec_td", "rec TD"),
    ("fum_lost", "fum lost"),
    ("sack", "sack"),
    ("int", "INT"),
    ("fum_rec", "fum rec"),
    ("def_td", "def TD"),
    ("pts_allow", "pts allowed"),
    ("fgm", "FG"),
    ("xpm", "XP"),
)
_SKIP_POINTS = {"pts_ppr", "pts_std", "pts_half_ppr"}


class RecentGame(BaseModel):
    week: int
    opponent: str | None = None
    home: bool | None = None
    fantasy_points: float | None = None
    points_label: str
    summary: str
    stats: dict[str, float] = {}


def has_stat_line(raw: dict | None) -> bool:
    if not raw:
        return False
    if any(raw.get(key) is not None for key, _label in COUNTING):
        return True
    return any(raw.get(key) is not None for key in _SKIP_POINTS)


def _format_value(value: float) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"


def summarize_stats(raw: dict) -> str:
    parts: list[str] = []
    for key, label in COUNTING:
        value = raw.get(key)
        if value is None:
            continue
        try:
            parts.append(f"{_format_value(float(value))} {label}")
        except (TypeError, ValueError):
            continue
    return ", ".join(parts)


def _scoring_column(scoring: dict) -> tuple[str, str]:
    try:
        rec = float(scoring.get("rec") or 0)
    except (TypeError, ValueError):
        rec = 0.0
    if rec >= 1:
        return "pts_ppr", "Sleeper PPR"
    if rec <= 0:
        return "pts_std", "Sleeper standard"
    return "pts_half_ppr", "Sleeper half PPR"


def score_stats(raw: dict, scoring: dict | None) -> tuple[float | None, str]:
    """League points when the stat keys overlap the scoring settings, else Sleeper's column."""
    scoring = scoring or {}
    total = 0.0
    used = False
    for key, value in raw.items():
        if key in _SKIP_POINTS or value is None or key not in scoring:
            continue
        try:
            total += float(value) * float(scoring[key])
            used = True
        except (TypeError, ValueError):
            continue
    if used:
        return round(total, 1), "This league"
    column, label = _scoring_column(scoring)
    value = raw.get(column)
    if value is None:
        return None, label
    try:
        return round(float(value), 1), label
    except (TypeError, ValueError):
        return None, label


def recent_game(
    *,
    week: int,
    raw: dict,
    scoring: dict | None,
    opponent: str | None,
    home: bool | None,
) -> RecentGame | None:
    if not has_stat_line(raw):
        return None
    points, label = score_stats(raw, scoring)
    summary = summarize_stats(raw)
    if not summary and points is None:
        return None
    stats: dict[str, float] = {}
    for key, _label in COUNTING:
        value = raw.get(key)
        if value is None:
            continue
        try:
            stats[key] = float(value)
        except (TypeError, ValueError):
            continue
    return RecentGame(
        week=week,
        opponent=opponent,
        home=home,
        fantasy_points=points,
        points_label=label,
        summary=summary or "Stat line posted",
        stats=stats,
    )


class SleeperWeeklyStats:
    def __init__(self, cache_dir: Path, base_url: str, ttl_seconds: int = 3600):
        self.cache_dir = cache_dir
        self.base_url = base_url.rstrip("/")
        self.ttl_seconds = ttl_seconds
        self._memory: dict[tuple[int, int], tuple[float, dict]] = {}
        self._lock = asyncio.Lock()

    def _path(self, season: int) -> Path:
        return self.cache_dir / f"sleeper_stats_{season}.json"

    def _read_disk(self, season: int) -> dict:
        path = self._path(season)
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_disk(self, season: int, weeks: dict) -> None:
        path = self._path(season)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"weeks": weeks}), encoding="utf-8")
        tmp.replace(path)

    async def week(self, season: int, week: int) -> dict:
        key = (season, week)
        now = time.time()
        cached = self._memory.get(key)
        if cached and now - cached[0] < self.ttl_seconds:
            return cached[1]
        disk = self._read_disk(season).get("weeks", {}).get(str(week))
        if isinstance(disk, dict) and now - float(disk.get("fetched_at") or 0) < self.ttl_seconds:
            stats = disk.get("stats") if isinstance(disk.get("stats"), dict) else {}
            self._memory[key] = (float(disk["fetched_at"]), stats)
            return stats
        async with self._lock:
            cached = self._memory.get(key)
            if cached and now - cached[0] < self.ttl_seconds:
                return cached[1]
            stats = await self._fetch(season, week)
            fetched = time.time()
            self._memory[key] = (fetched, stats)
            try:
                stored = self._read_disk(season)
                weeks = stored.get("weeks") if isinstance(stored.get("weeks"), dict) else {}
                weeks[str(week)] = {"fetched_at": fetched, "stats": stats}
                self._write_disk(season, weeks)
            except OSError as exc:
                log.warning("sleeper.stats_cache_failed", error=str(exc))
            return stats

    async def _fetch(self, season: int, week: int) -> dict:
        url = f"{self.base_url}/stats/nfl/regular/{season}/{week}"
        try:
            async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "fantasy-ai/0.1"}) as client:
                response = await client.get(url)
                if response.status_code == 404:
                    return {}
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("sleeper.stats_week_failed", season=season, week=week, error=str(exc))
            return {}
        return body if isinstance(body, dict) else {}

    async def recent(
        self,
        sleeper_id: str,
        season: int,
        through_week: int,
        *,
        scoring: dict | None,
        opponents: dict[int, tuple[str | None, bool | None]],
        limit: int = 5,
    ) -> list[RecentGame]:
        weeks = list(range(max(through_week, 1), 0, -1))
        blobs = await asyncio.gather(*(self.week(season, week) for week in weeks))
        games: list[RecentGame] = []
        for week, blob in zip(weeks, blobs, strict=True):
            raw = blob.get(sleeper_id)
            if not isinstance(raw, dict):
                continue
            opponent, home = opponents.get(week, (None, None))
            game = recent_game(week=week, raw=raw, scoring=scoring, opponent=opponent, home=home)
            if game is None:
                continue
            games.append(game)
            if len(games) >= limit:
                break
        return games
