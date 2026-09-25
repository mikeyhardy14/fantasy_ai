"""ESPN public scoreboard: schedule and the posted total/spread.

Eighteen weekly calls are cached on disk for a few hours. A failed fetch keeps
the last good file. Weeks with no events are omitted, so an unpublished week
is not treated as a bye.
"""

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.core.logging import get_logger
from app.nfl_data.base import ScheduleGame
from app.nfl_data.market import BookPrice, consensus, parse_american
from app.nfl_data.teams import app_team

log = get_logger(__name__)

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
REGULAR_SEASON_WEEKS = range(1, 19)


class Game:
    def __init__(
        self,
        week: int,
        opponent: str | None,
        home: bool | None,
        spread: float | None,
        total: float | None,
        implied_points: float | None,
        win_probability: float | None = None,
        book_count: int = 0,
        books: list[str] | None = None,
        starts_at: str | None = None,
        state: str | None = None,
    ):
        self.week = week
        self.opponent = opponent
        self.home = home
        self.spread = spread
        self.total = total
        self.implied_points = implied_points
        self.win_probability = win_probability
        self.book_count = book_count
        self.books = list(books or [])
        self.starts_at = starts_at
        self.state = state if state in {"pre", "in", "post"} else None

    def as_schedule(self) -> ScheduleGame:
        return ScheduleGame(
            week=self.week,
            opponent=self.opponent,
            home=self.home,
            spread=self.spread,
            total=self.total,
            implied_points=self.implied_points,
            win_probability=self.win_probability,
            book_count=self.book_count,
            books=list(self.books),
            starts_at=self.starts_at,
            state=self.state,
        )

    def to_json(self) -> dict:
        return {
            "opponent": self.opponent,
            "home": self.home,
            "spread": self.spread,
            "total": self.total,
            "implied": self.implied_points,
            "win_probability": self.win_probability,
            "book_count": self.book_count,
            "books": self.books,
            "starts_at": self.starts_at,
            "state": self.state,
        }

    @classmethod
    def from_json(cls, week: int, raw: dict) -> "Game":
        return cls(
            week=week,
            opponent=raw.get("opponent"),
            home=raw.get("home"),
            spread=raw.get("spread"),
            total=raw.get("total"),
            implied_points=raw.get("implied"),
            win_probability=raw.get("win_probability"),
            book_count=int(raw.get("book_count") or 0),
            books=list(raw.get("books") or []),
            starts_at=raw.get("starts_at"),
            state=raw.get("state"),
        )


class SeasonBoard:
    """Published weeks only. A team missing from a published week is on bye."""

    def __init__(self, weeks: dict[int, dict[str, Game]]):
        self.weeks = weeks
        self._known: set[str] = set()
        for slate in weeks.values():
            self._known.update(slate)

    def game(self, nfl_team: str, week: int) -> Game | None:
        slate = self.weeks.get(week)
        if not slate:
            return None
        key = app_team(nfl_team)
        found = slate.get(key)
        if found is not None:
            return found
        if key in self._known:
            return Game(week, None, None, None, None, None)
        return None

    def bye_week(self, nfl_team: str) -> int | None:
        key = app_team(nfl_team)
        if key not in self._known:
            return None
        for week in sorted(self.weeks):
            if key not in self.weeks[week]:
                return week
        return None

    def season(self, nfl_team: str) -> list[ScheduleGame]:
        key = app_team(nfl_team)
        if key not in self._known:
            return []
        games: list[ScheduleGame] = []
        for week in sorted(self.weeks):
            game = self.weeks[week].get(key) or Game(week, None, None, None, None, None)
            games.append(game.as_schedule())
        return games


def _kickoff(event: dict, comp: dict) -> tuple[str | None, str | None]:
    state = None
    for node in (comp, event):
        status = (node.get("status") or {}).get("type") or {}
        candidate = status.get("state")
        if candidate in {"pre", "in", "post"}:
            state = candidate
            break
    starts = event.get("date") or comp.get("date") or comp.get("startDate")
    return state, starts if isinstance(starts, str) else None


def _moneyline(odds: dict, side: str) -> float | None:
    moneyline = odds.get("moneyline") or {}
    side_node = moneyline.get(side) or {}
    if isinstance(side_node, dict):
        close = side_node.get("close") or {}
        parsed = parse_american(close.get("odds") if isinstance(close, dict) else None)
        if parsed is None:
            parsed = parse_american(side_node.get("odds"))
        if parsed is not None:
            return parsed
    team_odds = odds.get("homeTeamOdds" if side == "home" else "awayTeamOdds") or {}
    if isinstance(team_odds, dict):
        return parse_american(team_odds.get("moneyLine"))
    return None


def _books(raw: object) -> list[BookPrice]:
    entries = raw if isinstance(raw, list) else [raw] if isinstance(raw, dict) else []
    books: list[BookPrice] = []
    for odds in entries:
        if not isinstance(odds, dict):
            continue
        point_spread = odds.get("pointSpread") or {}
        home_spread = _line(point_spread.get("home") if isinstance(point_spread, dict) else None)
        if home_spread is None:
            home_spread = _number(odds.get("spread"))
        provider = odds.get("provider") or {}
        name = "Book"
        if isinstance(provider, dict):
            name = str(provider.get("name") or provider.get("displayName") or name)
        books.append(
            BookPrice(
                name=name,
                home_spread=home_spread,
                total=_number(odds.get("overUnder")),
                home_ml=_moneyline(odds, "home"),
                away_ml=_moneyline(odds, "away"),
            )
        )
    return books


def _line(side: dict | None) -> float | None:
    if not side:
        return None
    raw = (side.get("close") or {}).get("line")
    if raw is None:
        return None
    try:
        return float(str(raw))
    except (TypeError, ValueError):
        return None


def _number(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


@dataclass
class GameSummary:
    away: str
    home: str
    away_score: int | None
    home_score: int | None
    state: str | None
    detail: str | None
    summary: str | None
    broadcast: str | None


def _score(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _summary_text(state: str | None, situation: dict) -> str | None:
    last = situation.get("lastPlay") if isinstance(situation.get("lastPlay"), dict) else {}
    parts: list[str] = []
    text = last.get("text") if isinstance(last, dict) else None
    if isinstance(text, str) and text.strip():
        parts.append(text.strip().rstrip("."))
    drive = (last.get("drive") or {}).get("description") if isinstance(last, dict) else None
    if state == "in" and isinstance(drive, str) and drive.strip():
        parts.append(drive.strip())
    down = situation.get("downDistanceText")
    if state == "in" and isinstance(down, str) and down.strip():
        parts.append(down.strip())
    if not parts:
        return None
    return " · ".join(parts)


def parse_game_summaries(payload: dict) -> list[GameSummary]:
    """One scoreboard into a slate: score, clock, and the latest play."""
    rows: list[GameSummary] = []
    for event in payload.get("events") or []:
        comp = (event.get("competitions") or [{}])[0]
        home: tuple[str, int | None] | None = None
        away: tuple[str, int | None] | None = None
        for competitor in comp.get("competitors") or []:
            abbr = app_team((competitor.get("team") or {}).get("abbreviation"))
            side = competitor.get("homeAway")
            if not abbr or side not in {"home", "away"}:
                continue
            pair = (abbr, _score(competitor.get("score")))
            if side == "home":
                home = pair
            else:
                away = pair
        if home is None or away is None:
            continue
        state, _starts = _kickoff(event, comp)
        status = (comp.get("status") or {}).get("type") or {}
        detail = status.get("shortDetail")
        situation = comp.get("situation") if isinstance(comp.get("situation"), dict) else {}
        broadcasts = comp.get("broadcasts") or []
        network = None
        if broadcasts and isinstance(broadcasts[0], dict):
            names = broadcasts[0].get("names") or []
            if names:
                network = str(names[0])
        rows.append(
            GameSummary(
                away=away[0],
                home=home[0],
                away_score=away[1],
                home_score=home[1],
                state=state,
                detail=detail if isinstance(detail, str) else None,
                summary=_summary_text(state, situation),
                broadcast=network,
            )
        )
    return rows


def parse_scoreboard(payload: dict, week: int) -> dict[str, Game]:
    """One scoreboard response into games keyed by the app's team code."""
    games: dict[str, Game] = {}
    for event in payload.get("events") or []:
        comp = (event.get("competitions") or [{}])[0]
        sides: dict[str, str] = {}
        for competitor in comp.get("competitors") or []:
            abbr = app_team((competitor.get("team") or {}).get("abbreviation"))
            home_away = competitor.get("homeAway")
            if abbr and home_away in {"home", "away"}:
                sides[home_away] = abbr
        home, away = sides.get("home"), sides.get("away")
        if not home or not away:
            continue
        state, starts_at = _kickoff(event, comp)
        agreed = consensus(_books(comp.get("odds")))
        home_spread = agreed.home_spread
        away_spread = -home_spread if home_spread is not None else None
        total = agreed.total
        for team, opponent, spread, implied, win, is_home in (
            (home, away, home_spread, agreed.home_implied, agreed.home_win_probability, True),
            (away, home, away_spread, agreed.away_implied, None if agreed.home_win_probability is None else 1 - agreed.home_win_probability, False),
        ):
            games[team] = Game(
                week,
                opponent,
                is_home,
                spread,
                total,
                implied,
                win_probability=win,
                book_count=agreed.book_count,
                books=agreed.books,
                starts_at=starts_at,
                state=state,
            )
    return games


class ESPNScheduleClient:
    def __init__(self, cache_dir: Path, ttl_seconds: int = 6 * 3600):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self._memory: dict[int, tuple[float, SeasonBoard]] = {}
        self._live: dict[tuple[int, int], tuple[float, dict[str, Game], list[GameSummary]]] = {}
        self._lock = asyncio.Lock()

    def _path(self, season: int) -> Path:
        return self.cache_dir / f"espn_nfl_{season}.json"

    def _read_disk(self, season: int) -> tuple[float, SeasonBoard] | None:
        path = self._path(season)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("schema") != 3:
                return None
            fetched = float(raw.get("fetched_at") or 0)
            weeks: dict[int, dict[str, Game]] = {}
            for week, slate in (raw.get("weeks") or {}).items():
                weeks[int(week)] = {team: Game.from_json(int(week), game) for team, game in slate.items()}
            return fetched, SeasonBoard(weeks)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            log.warning("espn.cache_unreadable", path=str(path), error=str(exc))
            return None

    def _write_disk(self, season: int, board: SeasonBoard, fetched_at: float) -> None:
        path = self._path(season)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": 3,
            "fetched_at": fetched_at,
            "season": season,
            "weeks": {
                str(week): {team: game.to_json() for team, game in slate.items()}
                for week, slate in board.weeks.items()
            },
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(path)

    def _fresh(self, season: int) -> SeasonBoard | None:
        now = time.time()
        memory = self._memory.get(season)
        if memory and now - memory[0] < self.ttl_seconds:
            return memory[1]
        disk = self._read_disk(season)
        if disk and now - disk[0] < self.ttl_seconds:
            self._memory[season] = disk
            return disk[1]
        return None

    async def _fetch(self, season: int) -> SeasonBoard:
        weeks: dict[int, dict[str, Game]] = {}
        timeout = httpx.Timeout(20.0)
        headers = {"User-Agent": "fantasy-ai/0.1"}
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:

            async def one(week: int) -> tuple[int, dict[str, Game] | None]:
                try:
                    response = await client.get(
                        SCOREBOARD_URL,
                        params={"dates": str(season), "seasontype": "2", "week": str(week)},
                    )
                    response.raise_for_status()
                    return week, parse_scoreboard(response.json(), week)
                except (httpx.HTTPError, ValueError) as exc:
                    log.warning("espn.week_failed", season=season, week=week, error=str(exc))
                    return week, None

            results = await asyncio.gather(*(one(week) for week in REGULAR_SEASON_WEEKS))
        for week, games in results:
            if games:
                weeks[week] = games
        return SeasonBoard(weeks)

    async def live_week(self, season: int, week: int) -> dict[str, Game]:
        """One scoreboard, cached briefly so kickoff status stays current."""
        key = (season, week)
        now = time.time()
        cached = self._live.get(key)
        if cached and now - cached[0] < 45:
            return cached[1]
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0), headers={"User-Agent": "fantasy-ai/0.1"}) as client:
                response = await client.get(
                    SCOREBOARD_URL,
                    params={"dates": str(season), "seasontype": "2", "week": str(week)},
                )
                response.raise_for_status()
                payload = response.json()
                games = parse_scoreboard(payload, week)
                summaries = parse_game_summaries(payload)
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("espn.live_week_failed", season=season, week=week, error=str(exc))
            return cached[1] if cached else {}
        self._live[key] = (time.time(), games, summaries)
        return games

    async def live_summaries(self, season: int, week: int) -> list[GameSummary]:
        await self.live_week(season, week)
        cached = self._live.get((season, week))
        return list(cached[2]) if cached else []

    async def load(self, season: int) -> SeasonBoard:
        fresh = self._fresh(season)
        if fresh is not None:
            return fresh
        async with self._lock:
            fresh = self._fresh(season)
            if fresh is not None:
                return fresh
            board = await self._fetch(season)
            if board.weeks:
                fetched = time.time()
                self._memory[season] = (fetched, board)
                try:
                    self._write_disk(season, board, fetched)
                except OSError as exc:
                    log.warning("espn.cache_write_failed", error=str(exc))
                return board
            stale = self._read_disk(season)
            if stale is not None:
                log.warning("espn.using_stale_cache", season=season)
                self._memory[season] = stale
                return stale[1]
            return board
