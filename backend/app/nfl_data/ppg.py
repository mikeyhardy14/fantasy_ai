"""Season points-per-game from Sleeper and ESPN, blended into a week projection.

Sleeper publishes season totals on `/stats/nfl/regular/{season}`. ESPN publishes
season averages on the public fantasy league-defaults board. When both exist we
average them; otherwise the available source stands alone.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx
from pydantic import BaseModel

from app.core.logging import get_logger
from app.nfl_data.base import PlayerProjection

log = get_logger(__name__)

ESPN_DEFAULTS_URL = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/"
    "{season}/segments/0/leaguedefaults/{scoring_id}"
)


class SourcePpg(BaseModel):
    points_per_game: float
    season_points: float | None = None
    games_played: int | None = None
    source: str


class BlendedPpg(BaseModel):
    points_per_game: float
    sleeper: SourcePpg | None = None
    espn: SourcePpg | None = None
    note: str


def scoring_column(scoring: dict | None) -> tuple[str, str]:
    try:
        rec = float((scoring or {}).get("rec") or 0)
    except (TypeError, ValueError):
        rec = 0.0
    if rec >= 1:
        return "pts_ppr", "Sleeper PPR"
    if rec <= 0:
        return "pts_std", "Sleeper standard"
    return "pts_half_ppr", "Sleeper half PPR"


def espn_scoring_ids(scoring: dict | None) -> list[int]:
    """ESPN league-default boards: 1 = standard, 3 = PPR. Half-PPR averages both."""
    try:
        rec = float((scoring or {}).get("rec") or 0)
    except (TypeError, ValueError):
        rec = 0.0
    if rec >= 1:
        return [3]
    if rec <= 0:
        return [1]
    return [1, 3]


def blend_ppg(sleeper: SourcePpg | None, espn: SourcePpg | None) -> BlendedPpg | None:
    if sleeper is None and espn is None:
        return None
    if sleeper is not None and espn is not None:
        points = round((sleeper.points_per_game + espn.points_per_game) / 2, 1)
        return BlendedPpg(
            points_per_game=points,
            sleeper=sleeper,
            espn=espn,
            note=(
                f"{points:g} PPG averages Sleeper ({sleeper.points_per_game:g}) "
                f"and ESPN ({espn.points_per_game:g})."
            ),
        )
    sole = sleeper or espn
    assert sole is not None
    return BlendedPpg(
        points_per_game=sole.points_per_game,
        sleeper=sleeper,
        espn=espn,
        note=f"{sole.points_per_game:g} PPG from {sole.source}.",
    )


def project_from_ppg(blended: BlendedPpg, week: int) -> PlayerProjection:
    detail: dict[str, float] = {
        "ppg": blended.points_per_game,
        "ppg_blend": 1.0,
    }
    if blended.sleeper is not None:
        detail["sleeper_ppg"] = blended.sleeper.points_per_game
        if blended.sleeper.season_points is not None:
            detail["sleeper_season_points"] = blended.sleeper.season_points
        if blended.sleeper.games_played is not None:
            detail["sleeper_games"] = float(blended.sleeper.games_played)
    if blended.espn is not None:
        detail["espn_ppg"] = blended.espn.points_per_game
        if blended.espn.season_points is not None:
            detail["espn_season_points"] = blended.espn.season_points
        if blended.espn.games_played is not None:
            detail["espn_games"] = float(blended.espn.games_played)
    return PlayerProjection(
        week=week,
        points=blended.points_per_game,
        source="ppg",
        detail=detail,
        note=blended.note,
    )


def sleeper_source(raw: dict | None, scoring: dict | None) -> SourcePpg | None:
    if not isinstance(raw, dict):
        return None
    column, label = scoring_column(scoring)
    total = raw.get(column)
    games = raw.get("gp") or raw.get("gms_active")
    if total is None or not games:
        return None
    try:
        points = float(total)
        played = int(float(games))
    except (TypeError, ValueError):
        return None
    if played <= 0:
        return None
    return SourcePpg(
        points_per_game=round(points / played, 1),
        season_points=round(points, 1),
        games_played=played,
        source=label,
    )


def espn_source(applied_total: float | None, applied_average: float | None) -> SourcePpg | None:
    if applied_average is None:
        return None
    try:
        ppg = round(float(applied_average), 1)
    except (TypeError, ValueError):
        return None
    if ppg <= 0:
        return None
    season = None
    games = None
    if applied_total is not None:
        try:
            season = round(float(applied_total), 1)
            if ppg > 0:
                games = max(1, int(round(float(applied_total) / float(applied_average))))
        except (TypeError, ValueError):
            season = None
    return SourcePpg(
        points_per_game=ppg,
        season_points=season,
        games_played=games,
        source="ESPN",
    )


def _season_actual(stats: list | None) -> tuple[float | None, float | None]:
    for row in stats or []:
        if not isinstance(row, dict):
            continue
        if (
            row.get("scoringPeriodId") == 0
            and row.get("statSourceId") == 0
            and row.get("statSplitTypeId") in (0, None)
        ):
            return row.get("appliedTotal"), row.get("appliedAverage")
    return None, None


class SleeperSeasonStats:
    """Season totals published by Sleeper for every NFL player."""

    def __init__(self, cache_dir: Path, base_url: str, ttl_seconds: int = 3600):
        self.cache_dir = cache_dir
        self.base_url = base_url.rstrip("/")
        self.ttl_seconds = ttl_seconds
        self._memory: dict[int, tuple[float, dict[str, dict]]] = {}
        self._lock = asyncio.Lock()

    def _path(self, season: int) -> Path:
        return self.cache_dir / f"sleeper_season_{season}.json"

    async def season(self, season: int) -> dict[str, dict]:
        now = time.time()
        cached = self._memory.get(season)
        if cached and now - cached[0] < self.ttl_seconds:
            return cached[1]
        disk = self._read_disk(season, now)
        if disk is not None:
            self._memory[season] = (now, disk)
            return disk
        async with self._lock:
            cached = self._memory.get(season)
            if cached and time.time() - cached[0] < self.ttl_seconds:
                return cached[1]
            stats = await self._fetch(season)
            fetched = time.time()
            self._memory[season] = (fetched, stats)
            if stats:
                self._write_disk(season, fetched, stats)
            return stats

    async def player(self, season: int, sleeper_id: str) -> dict | None:
        blob = await self.season(season)
        row = blob.get(str(sleeper_id))
        return row if isinstance(row, dict) else None

    def _read_disk(self, season: int, now: float) -> dict[str, dict] | None:
        path = self._path(season)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if now - float(raw.get("fetched_at") or 0) >= self.ttl_seconds:
                return None
            stats = raw.get("stats")
            return stats if isinstance(stats, dict) else {}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None

    def _write_disk(self, season: int, fetched: float, stats: dict) -> None:
        path = self._path(season)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"fetched_at": fetched, "stats": stats}), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            log.warning("sleeper.season_cache_failed", error=str(exc))

    async def _fetch(self, season: int) -> dict[str, dict]:
        url = f"{self.base_url}/stats/nfl/regular/{season}"
        try:
            async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": "fantasy-ai/0.1"}) as client:
                response = await client.get(url)
                if response.status_code == 404:
                    return {}
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("sleeper.season_failed", season=season, error=str(exc))
            return {}
        if not isinstance(body, dict):
            return {}
        return {str(key): value for key, value in body.items() if isinstance(value, dict)}


class EspnPpgClient:
    """Season PPG from ESPN's public fantasy league-defaults player pool."""

    def __init__(self, cache_dir: Path, ttl_seconds: int = 6 * 3600, page_size: int = 50, max_players: int = 800):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.page_size = page_size
        self.max_players = max_players
        self._memory: dict[tuple[int, int], tuple[float, dict[str, SourcePpg]]] = {}
        self._lock = asyncio.Lock()

    def _path(self, season: int, scoring_id: int) -> Path:
        return self.cache_dir / f"espn_ppg_{season}_{scoring_id}.json"

    async def player(self, season: int, espn_id: str, scoring: dict | None) -> SourcePpg | None:
        ids = espn_scoring_ids(scoring)
        rows = await asyncio.gather(*(self._board(season, sid) for sid in ids))
        sources = [board.get(str(espn_id)) for board in rows]
        present = [row for row in sources if row is not None]
        if not present:
            return None
        if len(present) == 1:
            return present[0]
        ppg = round(sum(row.points_per_game for row in present) / len(present), 1)
        season_points = None
        totals = [row.season_points for row in present if row.season_points is not None]
        if totals:
            season_points = round(sum(totals) / len(totals), 1)
        games = next((row.games_played for row in present if row.games_played), None)
        return SourcePpg(
            points_per_game=ppg,
            season_points=season_points,
            games_played=games,
            source="ESPN half PPR",
        )

    async def _board(self, season: int, scoring_id: int) -> dict[str, SourcePpg]:
        key = (season, scoring_id)
        now = time.time()
        cached = self._memory.get(key)
        if cached and now - cached[0] < self.ttl_seconds:
            return cached[1]
        disk = self._read_disk(season, scoring_id, now)
        if disk is not None:
            self._memory[key] = (now, disk)
            return disk
        async with self._lock:
            cached = self._memory.get(key)
            if cached and time.time() - cached[0] < self.ttl_seconds:
                return cached[1]
            board = await self._fetch(season, scoring_id)
            fetched = time.time()
            self._memory[key] = (fetched, board)
            if board:
                self._write_disk(season, scoring_id, fetched, board)
            return board

    def _read_disk(self, season: int, scoring_id: int, now: float) -> dict[str, SourcePpg] | None:
        path = self._path(season, scoring_id)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if now - float(raw.get("fetched_at") or 0) >= self.ttl_seconds:
                return None
            rows = raw.get("players")
            if not isinstance(rows, dict):
                return {}
            return {pid: SourcePpg.model_validate(row) for pid, row in rows.items()}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None

    def _write_disk(self, season: int, scoring_id: int, fetched: float, board: dict[str, SourcePpg]) -> None:
        path = self._path(season, scoring_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "fetched_at": fetched,
                "players": {pid: row.model_dump() for pid, row in board.items()},
            }
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            log.warning("espn.ppg_cache_failed", error=str(exc))

    async def _fetch(self, season: int, scoring_id: int) -> dict[str, SourcePpg]:
        url = ESPN_DEFAULTS_URL.format(season=season, scoring_id=scoring_id)
        board: dict[str, SourcePpg] = {}
        offset = 0
        try:
            async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": "fantasy-ai/0.1"}) as client:
                while offset < self.max_players:
                    filt = {
                        "players": {
                            "limit": self.page_size,
                            "offset": offset,
                            "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
                        }
                    }
                    response = await client.get(
                        url,
                        params={"view": "kona_player_info"},
                        headers={"X-Fantasy-Filter": json.dumps(filt), "Accept": "application/json"},
                    )
                    if response.status_code == 404:
                        return board
                    response.raise_for_status()
                    body = response.json()
                    players = body.get("players") if isinstance(body, dict) else None
                    if not isinstance(players, list) or not players:
                        break
                    for row in players:
                        if not isinstance(row, dict):
                            continue
                        player = row.get("player") if isinstance(row.get("player"), dict) else row
                        espn_id = player.get("id") if isinstance(player, dict) else None
                        if espn_id is None:
                            continue
                        total, average = _season_actual(player.get("stats") if isinstance(player, dict) else None)
                        source = espn_source(total, average)
                        if source is not None:
                            board[str(espn_id)] = source
                    if len(players) < self.page_size:
                        break
                    offset += self.page_size
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("espn.ppg_failed", season=season, scoring_id=scoring_id, error=str(exc))
        return board
