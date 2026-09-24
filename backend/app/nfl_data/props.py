"""DraftKings player props from the ESPN odds feed.

The posted line is the expected stat. Fantasy points are that line times the
league's scoring weight. 100.5 rush yards at 0.1 per yard is 10.0. A stat
with no posted line is left out. Tests never call the network.
"""

import asyncio
import json
import math
import re
import time
from pathlib import Path

import httpx

from app.core.logging import get_logger
from app.nfl_data.base import PlayerProjection
from app.nfl_data.market import american_probability, fair_home_probability, parse_american
from app.nfl_data.sleeper_stats import score_stats
from app.nfl_data.vegas import normalize_position

log = get_logger(__name__)

_ATHLETE = re.compile(r"athletes/(\d+)")

# Full-game totals only. Milestones, halves, and combined yards would double count.
PROP_STATS: dict[str, str] = {
    "Total Passing Yards (incl. overtime)": "pass_yd",
    "Total Passing Touchdowns (incl. overtime)": "pass_td",
    "Total Passing Interceptions (incl. overtime)": "pass_int",
    "Total Rushing Yards (incl. overtime)": "rush_yd",
    "Total Receiving Yards (incl. overtime)": "rec_yd",
    "Total Receptions (incl. overtime)": "rec",
    "Total Field Goals Made (incl. overtime)": "fgm",
    "Total Extra Points Made (incl. overtime)": "xpm",
    "Total Sacks (incl. overtime)": "sack",
}

STAT_LABELS: tuple[tuple[str, str], ...] = (
    ("pass_yd", "Pass yds"),
    ("pass_td", "Pass TD"),
    ("pass_int", "INT"),
    ("rush_yd", "Rush yds"),
    ("rush_td", "Rush TD"),
    ("rec", "Rec"),
    ("rec_yd", "Rec yds"),
    ("rec_td", "Rec TD"),
    ("fgm", "FG"),
    ("xpm", "XP"),
    ("sack", "Sacks"),
)

# DraftKings subcategory boards. Yardage is the main over/under. Touchdowns and
# interceptions also carry a price, which is turned into an expected count.
DK_BOARDS: tuple[tuple[int, int, str], ...] = (
    (1001, 9514, "rush_yd"),
    (1342, 14114, "rec_yd"),
    (1342, 14115, "rec"),
    (1000, 9524, "pass_yd"),
    (1000, 9525, "pass_td"),
    (1000, 15937, "pass_int"),
    (1743, 17061, "fgm"),
    (1743, 17060, "xpm"),
    (1003, 12438, "anytime"),
)
DK_URL = (
    "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusnj/v1/leagues/88808"
    "/categories/{category}/subcategories/{subcategory}"
)
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def norm_name(name: str) -> str:
    text = name.lower().replace(".", "").replace("'", "").replace("’", "")
    text = re.sub(r"[^a-z\s]", " ", text)
    return " ".join(part for part in text.split() if part not in _SUFFIXES)


def format_american(ml: float) -> str:
    number = int(round(ml))
    return f"+{number}" if number > 0 else str(number)


def expected_count(probability: float, minimum: int) -> float | None:
    """Poisson count whose chance of at least `minimum` events equals `probability`.

    Anytime touchdown and a 0.5 total are minimum 1, so the count is -ln(1 - p).
    A 1.5 total is the chance of 2 or more, and the count is solved to match that.
    """
    if probability <= 0 or probability >= 1 or minimum < 1:
        return None
    if minimum == 1:
        return -math.log(1 - probability)

    def tail(lam: float) -> float:
        cdf = sum(math.exp(-lam) * lam**k / math.factorial(k) for k in range(minimum))
        return 1 - cdf

    lo, hi = 0.01, 15.0
    if tail(hi) < probability:
        return None
    for _ in range(50):
        mid = (lo + hi) / 2
        if tail(mid) < probability:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _half_line(line: float) -> int | None:
    """0.5 -> 1, 1.5 -> 2. Whole-number lines are not a clean over/under."""
    if abs(line * 2 - round(line * 2)) > 1e-6:
        return None
    if abs(line - round(line)) < 1e-6:
        return None
    return int(math.floor(line)) + 1


def parse_dk_board(payload: dict, kind: str) -> dict[str, dict[str, float]]:
    """One DraftKings board into lines keyed by normalized player name."""
    markets = {item.get("id"): item for item in payload.get("markets") or [] if isinstance(item, dict)}
    found: dict[str, dict[str, float]] = {}
    for selection in payload.get("selections") or []:
        if not isinstance(selection, dict):
            continue
        participants = selection.get("participants") or []
        if not participants or not isinstance(participants[0], dict):
            continue
        name = norm_name(str(participants[0].get("name") or ""))
        if not name:
            continue
        market = markets.get(selection.get("marketId")) or {}
        odds = parse_american((selection.get("displayOdds") or {}).get("american"))
        if kind == "anytime":
            if market.get("name") != "Anytime TD Scorer" or odds is None:
                continue
            found.setdefault(name, {})["anytime_ml"] = odds
            continue
        if selection.get("main") is not True:
            continue
        outcome = selection.get("outcomeType")
        row = found.setdefault(name, {})
        if outcome == "Over" and selection.get("points") is not None:
            try:
                row[kind] = float(selection["points"])
            except (TypeError, ValueError):
                continue
            if odds is not None:
                row[f"{kind}_over"] = odds
        elif outcome == "Under" and odds is not None:
            row[f"{kind}_under"] = odds
    return found


def parse_prop_items(items: list) -> dict[str, dict[str, float]]:
    """ESPN athlete id to the posted full-game lines."""
    found: dict[str, dict[str, float]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = PROP_STATS.get(((item.get("type") or {}).get("name")))
        if not key:
            continue
        target = ((item.get("current") or {}).get("target") or {}).get("value")
        if target is None:
            continue
        ref = (item.get("athlete") or {}).get("$ref") or ""
        match = _ATHLETE.search(str(ref))
        if not match:
            continue
        try:
            value = float(target)
        except (TypeError, ValueError):
            continue
        found.setdefault(match.group(1), {})[key] = value
    return found


def _priced_count(stats: dict[str, float], prefix: str) -> tuple[float, float, float, float] | None:
    """Over/under odds to (posted line, fair probability, minimum count, expected count)."""
    line = stats.get(prefix)
    over = stats.get(f"{prefix}_over")
    under = stats.get(f"{prefix}_under")
    if line is None or over is None or under is None:
        return None
    minimum = _half_line(line)
    fair = fair_home_probability(over, under)
    if minimum is None or fair is None:
        return None
    lam = expected_count(fair, minimum)
    if lam is None:
        return None
    return line, fair, float(minimum), lam


def project_player_props(
    stats: dict[str, float],
    scoring: dict | None,
    *,
    week: int,
    position: str | None = None,
) -> PlayerProjection | None:
    """Fantasy points from posted lines. Touchdowns and interceptions use the odds."""
    scoring = scoring or {}
    pos = normalize_position(position)
    priced = dict(stats)
    detail_extra: dict[str, float] = {}
    if pos != "QB":
        priced.pop("pass_td", None)
        priced.pop("pass_int", None)
    else:
        for prefix, label_key in (("pass_td", "pass_td"), ("pass_int", "pass_int")):
            solved = _priced_count(priced, prefix)
            if solved is None:
                priced.pop(prefix, None)
                continue
            line, fair, minimum, lam = solved
            priced[prefix] = lam
            detail_extra[f"{label_key}_ou"] = line
            detail_extra[f"{label_key}_p"] = fair
            detail_extra[f"{label_key}_min"] = minimum
            detail_extra[f"{label_key}_over"] = float(priced[f"{prefix}_over"])
            detail_extra[f"{label_key}_under"] = float(priced[f"{prefix}_under"])
    anytime = priced.get("anytime_ml")
    if anytime is not None and pos:
        chance = american_probability(anytime)
        lam = expected_count(chance, 1) if chance is not None else None
        if lam is not None:
            td_key = "rec_td" if pos in {"WR", "TE"} else "rush_td"
            if td_key not in scoring:
                other = "rush_td" if td_key == "rec_td" else "rec_td"
                td_key = other if other in scoring else td_key
            priced[td_key] = lam
            detail_extra["any_td_ml"] = float(anytime)
            detail_extra["any_td_p"] = chance or 0.0
            detail_extra["any_on_rush" if td_key == "rush_td" else "any_on_rec"] = 1.0
    points, _label = score_stats(priced, scoring)
    if points is None:
        return None
    detail: dict[str, float] = {"props": 1.0}
    for key, _label in STAT_LABELS:
        if key not in priced or key not in scoring:
            continue
        try:
            weight = float(scoring[key])
            line = float(priced[key])
        except (TypeError, ValueError):
            continue
        detail[key] = line
        detail[f"{key}_w"] = weight
    detail.update(detail_extra)
    if len(detail) == 1:
        return None
    return PlayerProjection(
        week=week,
        points=points,
        source="vegas",
        detail=detail,
        note="DraftKings prop lines",
    )


def prop_components(detail: dict | None) -> list[dict]:
    """Rows for the projection table. Touchdown and interception rows include the odds."""
    if not detail or detail.get("props") != 1:
        return []
    rows: list[dict] = []
    for key, label in STAT_LABELS:
        if key not in detail or f"{key}_w" not in detail:
            continue
        line = float(detail[key])
        weight = float(detail[f"{key}_w"])
        odds = None
        probability = None
        if key == "rush_td" and detail.get("any_on_rush") == 1:
            label = "Anytime TD"
            odds = format_american(detail["any_td_ml"])
            probability = detail.get("any_td_p")
        elif key == "rec_td" and detail.get("any_on_rec") == 1:
            label = "Anytime TD"
            odds = format_american(detail["any_td_ml"])
            probability = detail.get("any_td_p")
        elif key in {"pass_td", "pass_int"} and f"{key}_over" in detail and f"{key}_under" in detail:
            odds = f"{format_american(detail[f'{key}_over'])} / {format_american(detail[f'{key}_under'])}"
            probability = detail.get(f"{key}_p")
        rows.append(
            {
                "label": label,
                "line": line,
                "weight": weight,
                "points": round(line * weight, 2),
                "odds": odds,
                "probability": probability,
            }
        )
    return rows


def _sleeper_espn_ids(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("props.sleeper_ids_unreadable", error=str(exc))
        return {}
    if not isinstance(raw, dict):
        return {}
    ids: dict[str, str] = {}
    for sleeper_id, player in raw.items():
        if isinstance(player, dict) and player.get("espn_id"):
            ids[str(sleeper_id)] = str(player["espn_id"])
    return ids


class EspnPropClient:
    def __init__(self, cache_dir: Path, sleeper_players_path: Path, ttl_seconds: int = 1800):
        self.cache_dir = cache_dir
        self.sleeper_players_path = sleeper_players_path
        self.ttl_seconds = ttl_seconds
        self._memory: dict[tuple[int, int], tuple[float, dict[str, dict[str, float]]]] = {}
        self._sleeper_ids: dict[str, str] | None = None
        self._lock = asyncio.Lock()

    def espn_id_for(self, extra: dict | None, sleeper_id: str | None) -> str | None:
        stored = (extra or {}).get("espn_id")
        if stored:
            return str(stored)
        if not sleeper_id:
            return None
        if self._sleeper_ids is None:
            self._sleeper_ids = _sleeper_espn_ids(self.sleeper_players_path)
        return self._sleeper_ids.get(str(sleeper_id))

    def _path(self, season: int, week: int) -> Path:
        return self.cache_dir / f"dk_props_{season}_{week}.json"

    def _read_disk(self, season: int, week: int) -> tuple[float, dict[str, dict[str, float]]] | None:
        path = self._path(season, week)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            fetched = float(raw.get("fetched_at") or 0)
            players = raw.get("players") if isinstance(raw.get("players"), dict) else {}
            return fetched, players
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            log.warning("props.cache_unreadable", error=str(exc))
            return None

    def _write_disk(self, season: int, week: int, players: dict, fetched_at: float) -> None:
        path = self._path(season, week)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"fetched_at": fetched_at, "players": players}), encoding="utf-8")
        tmp.replace(path)

    async def lines(self, season: int, week: int) -> dict[str, dict[str, float]]:
        key = (season, week)
        now = time.time()
        cached = self._memory.get(key)
        if cached and now - cached[0] < self.ttl_seconds:
            return cached[1]
        disk = self._read_disk(season, week)
        if disk and now - disk[0] < self.ttl_seconds:
            self._memory[key] = disk
            return disk[1]
        async with self._lock:
            cached = self._memory.get(key)
            if cached and now - cached[0] < self.ttl_seconds:
                return cached[1]
            try:
                players = await self._fetch(season, week)
            except Exception as exc:
                log.warning("props.fetch_failed", season=season, week=week, error=str(exc))
                if disk:
                    self._memory[key] = disk
                    return disk[1]
                return {}
            fetched = time.time()
            self._memory[key] = (fetched, players)
            try:
                self._write_disk(season, week, players, fetched)
            except OSError as exc:
                log.warning("props.cache_write_failed", error=str(exc))
            return players

    async def project_named(
        self,
        name: str,
        position: str | None,
        season: int,
        week: int,
        scoring: dict | None,
    ) -> PlayerProjection | None:
        stats = (await self.lines(season, week)).get(norm_name(name))
        if not stats:
            return None
        return project_player_props(stats, scoring, week=week, position=position)

    async def _fetch(self, season: int, week: int) -> dict[str, dict[str, float]]:
        timeout = httpx.Timeout(25.0)
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:

            async def one(category: int, subcategory: int, kind: str) -> dict[str, dict[str, float]]:
                try:
                    response = await client.get(DK_URL.format(category=category, subcategory=subcategory))
                    response.raise_for_status()
                    return parse_dk_board(response.json(), kind)
                except (httpx.HTTPError, ValueError) as exc:
                    log.warning("props.board_failed", kind=kind, error=str(exc))
                    return {}

            parts = await asyncio.gather(*(one(category, subcategory, kind) for category, subcategory, kind in DK_BOARDS))
        merged: dict[str, dict[str, float]] = {}
        for part in parts:
            for name, stats in part.items():
                merged.setdefault(name, {}).update(stats)
        return merged
