"""NFLDataProvider backed by a JSON file.

File format (all sections optional):

{
  "bye_weeks": {"2026": {"KC": 6, "BUF": 12}},
  "schedule":  {"2026": {"1": {"KC": "BAL", "BAL": "KC"}}},
  "projections": {"2026": {"4": {"<player_key>": {"points": 18.4, "detail": {...}}}}},
  "season_stats": {"2026": {"<player_key>": {"games_played": 3, "fantasy_points": 55.2}}},
  "news": {"<player_key>": [{"headline": "...", "published_at": "..."}]}
}

The demo seed writes entries for demo players. For real leagues the file is
normally empty, so the app reports data as unavailable rather than guessing.
"""

import json
import time
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.nfl_data.base import (
    NFLDataProvider,
    PlayerNews,
    PlayerProjection,
    PlayerSeasonStats,
)

log = get_logger(__name__)


class LocalFileNFLDataProvider(NFLDataProvider):
    name = "local_file"

    def __init__(self, path: Path, reload_seconds: int = 30):
        self.path = path
        self.reload_seconds = reload_seconds
        self._data: dict[str, Any] = {}
        self._loaded_at = 0.0
        self._mtime = 0.0

    def _load(self) -> dict[str, Any]:
        now = time.time()
        if self._data and now - self._loaded_at < self.reload_seconds:
            return self._data
        self._loaded_at = now
        if not self.path.exists():
            self._data = {}
            return self._data
        try:
            mtime = self.path.stat().st_mtime
            if mtime != self._mtime or not self._data:
                with self.path.open("r", encoding="utf-8") as fh:
                    self._data = json.load(fh)
                self._mtime = mtime
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("nfl_data.load_failed", path=str(self.path), error=str(exc))
            self._data = {}
        return self._data

    def merge(self, extra: dict[str, Any]) -> None:
        """Deep-merge extra data into the file (used by the demo seed)."""
        data = self._load() if self.path.exists() else {}

        def _merge(a: dict, b: dict) -> dict:
            for k, v in b.items():
                if isinstance(v, dict) and isinstance(a.get(k), dict):
                    _merge(a[k], v)
                else:
                    a[k] = v
            return a

        merged = _merge(dict(data), extra)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=1)
        self._data = merged
        self._loaded_at = time.time()
        self._mtime = self.path.stat().st_mtime

    async def get_bye_week(self, nfl_team: str, season: int) -> int | None:
        byes = self._load().get("bye_weeks", {}).get(str(season), {})
        value = byes.get((nfl_team or "").upper())
        return int(value) if value is not None else None

    async def get_opponent(self, nfl_team: str, season: int, week: int) -> str | None:
        sched = self._load().get("schedule", {}).get(str(season), {}).get(str(week), {})
        return sched.get((nfl_team or "").upper())

    async def get_projection(self, player_key: str, season: int, week: int) -> PlayerProjection | None:
        proj = self._load().get("projections", {}).get(str(season), {}).get(str(week), {})
        raw = proj.get(player_key)
        if not raw:
            return None
        return PlayerProjection(
            week=week,
            points=float(raw["points"]),
            source=raw.get("source", self.name),
            detail=raw.get("detail", {}),
        )

    async def get_season_stats(self, player_key: str, season: int) -> PlayerSeasonStats | None:
        raw = self._load().get("season_stats", {}).get(str(season), {}).get(player_key)
        if not raw:
            return None
        gp = raw.get("games_played")
        fp = raw.get("fantasy_points")
        ppg = raw.get("fantasy_points_per_game")
        if ppg is None and gp and fp is not None:
            ppg = round(fp / gp, 2)
        return PlayerSeasonStats(
            season=season,
            games_played=gp,
            fantasy_points=fp,
            fantasy_points_per_game=ppg,
            detail=raw.get("detail", {}),
            source=raw.get("source", self.name),
        )

    async def get_news(self, player_key: str, limit: int = 3) -> list[PlayerNews]:
        items = self._load().get("news", {}).get(player_key, [])[:limit]
        return [PlayerNews(**item) for item in items]
