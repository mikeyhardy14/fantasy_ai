"""Injury designations from ESPN's league-wide NFL injury report.

Sleeper's player catalogue is meant to be fetched at most once a day, so its
injury labels miss practice-week changes and game-day inactives. ESPN's report
updates within minutes and also lists players who were just cleared ("Active").
Statuses are translated into the labels Sleeper uses so the rest of the app
(flags, IR eligibility, AI Management) reads them unchanged.

ESPN is not always ahead: a report can still carry last Sunday's tag after
Sleeper has posted this week's news. A report only wins when it is newer than
the player's latest Sleeper news. Players are matched by ESPN id, or by name
and team when Sleeper has no ESPN id for them (most depth players).
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from app.core.logging import get_logger
from app.models import Player
from app.nfl_data.teams import app_team

log = get_logger(__name__)

ESPN_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"

# ESPN fantasy designation -> the label Sleeper would use.
_STATUS = {
    "QUESTIONABLE": "Questionable",
    "DOUBTFUL": "Doubtful",
    "OUT": "Out",
    "INACTIVE": "Out",
    "IR": "IR",
    "IR-R": "IR",
    "IR-NFI": "IR",
    "PUP": "PUP",
    "PUP-R": "PUP",
    "PUP-P": "PUP",
    "SUSPENSION": "Sus",
    "SUSPENDED": "Sus",
    "SUS": "Sus",
}
_CLEARED = {"ACTIVE"}
# An "Active" entry this old is a past injury, not news; Sleeper's label stands.
_CLEARED_FOR = timedelta(days=14)
_ATHLETE_ID = re.compile(r"/id/(\d+)")
_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?")


@dataclass(frozen=True)
class InjuryReport:
    status: str | None  # Sleeper-style label; None means cleared to play
    body_part: str | None
    note: str | None
    updated_at: datetime | None
    name_key: str | None = None


def name_key(name: str | None, team: str | None) -> str | None:
    """Loose identity for players Sleeper has no ESPN id for: name without suffixes, plus team."""
    if not name or not team:
        return None
    letters = re.sub(r"[^a-z]", "", _SUFFIX.sub("", name.lower()))
    return f"{letters}|{app_team(team)}" if letters else None


def _parse_date(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _athlete_id(athlete: dict) -> str | None:
    if athlete.get("id"):
        return str(athlete["id"])
    for link in athlete.get("links") or []:
        match = _ATHLETE_ID.search(str((link or {}).get("href") or ""))
        if match:
            return match.group(1)
    return None


def _label(entry: dict) -> tuple[bool, str | None]:
    """(known, label). Unknown designations are skipped so Sleeper's label stands."""
    details = entry.get("details") if isinstance(entry.get("details"), dict) else {}
    fantasy = details.get("fantasyStatus") if isinstance(details.get("fantasyStatus"), dict) else {}
    for raw in (fantasy.get("abbreviation"), entry.get("status")):
        if not raw:
            continue
        key = str(raw).strip().upper()
        if key in _CLEARED:
            return True, None
        key = {"INJURED RESERVE": "IR"}.get(key, key)
        if key in _STATUS:
            return True, _STATUS[key]
    return False, None


def parse_injuries(body: dict, *, now: datetime | None = None) -> dict[str, InjuryReport]:
    """ESPN athlete id -> latest report."""
    now = now or datetime.now(UTC)
    reports: dict[str, InjuryReport] = {}
    for team in body.get("injuries") or []:
        for entry in (team or {}).get("injuries") or []:
            if not isinstance(entry, dict) or not isinstance(entry.get("athlete"), dict):
                continue
            espn_id = _athlete_id(entry["athlete"])
            if espn_id is None:
                continue
            known, label = _label(entry)
            if not known:
                continue
            updated = _parse_date(entry.get("date"))
            if label is None and (updated is None or now - updated > _CLEARED_FOR):
                continue
            previous = reports.get(espn_id)
            if previous and previous.updated_at and updated and previous.updated_at >= updated:
                continue
            details = entry.get("details") if isinstance(entry.get("details"), dict) else {}
            athlete = entry["athlete"]
            team = athlete.get("team") if isinstance(athlete.get("team"), dict) else {}
            reports[espn_id] = InjuryReport(
                status=label,
                body_part=(details.get("type") or None) if label else None,
                note=entry.get("shortComment") or None,
                updated_at=updated,
                name_key=name_key(athlete.get("displayName"), team.get("abbreviation")),
            )
    return reports


def _newer_than_sleeper(report: InjuryReport, player: Player) -> bool:
    news = (player.extra or {}).get("news_updated")
    if not news:
        return True
    if report.updated_at is None:
        return False
    try:
        return report.updated_at.timestamp() * 1000 > float(news)
    except (TypeError, ValueError):
        return True


def apply_injury_reports(players: Iterable[Player], reports: dict[str, InjuryReport]) -> int:
    """Overlay ESPN's designation where it is newer than Sleeper's news. Returns how many changed."""
    by_name: dict[str, InjuryReport | None] = {}
    for report in reports.values():
        if report.name_key:
            # Two ESPN players with one name on one team: too ambiguous to use.
            by_name[report.name_key] = None if report.name_key in by_name else report
    changed = 0
    for player in players:
        espn_id = (player.extra or {}).get("espn_id")
        if espn_id:
            report = reports.get(str(espn_id))
        else:
            key = name_key(player.name, player.nfl_team)
            report = by_name.get(key) if key else None
        if report is None or not _newer_than_sleeper(report, player):
            continue
        before = (player.injury_status, player.injury_body_part)
        player.injury_status = report.status
        player.injury_body_part = report.body_part
        player.extra = {
            **(player.extra or {}),
            "injury_source": "espn",
            "injury_updated_at": report.updated_at.isoformat() if report.updated_at else None,
            "injury_notes": report.note,
        }
        if before != (player.injury_status, player.injury_body_part):
            changed += 1
    return changed


class EspnInjuryClient:
    """Cached ESPN injury report. A failed fetch keeps the last good report."""

    def __init__(
        self,
        url: str = ESPN_INJURIES_URL,
        *,
        ttl_seconds: float = 600,
        retry_seconds: float = 60,
        timeout: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.url = url
        self.ttl_seconds = ttl_seconds
        self.retry_seconds = retry_seconds
        self.timeout = timeout
        self._transport = transport
        self._reports: dict[str, InjuryReport] = {}
        self._next_fetch = 0.0
        self._lock = asyncio.Lock()

    async def reports(self) -> dict[str, InjuryReport]:
        if time.monotonic() < self._next_fetch:
            return self._reports
        async with self._lock:
            if time.monotonic() < self._next_fetch:
                return self._reports
            try:
                self._reports = await self._fetch()
                self._next_fetch = time.monotonic() + self.ttl_seconds
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                log.warning("espn.injuries_failed", error=str(exc))
                self._next_fetch = time.monotonic() + self.retry_seconds
            return self._reports

    async def _fetch(self) -> dict[str, InjuryReport]:
        async with httpx.AsyncClient(
            timeout=self.timeout, transport=self._transport, headers={"User-Agent": "fantasy-ai/0.1"}
        ) as client:
            response = await client.get(self.url)
            response.raise_for_status()
            raw = response.content
        # The report is ~9MB; parse it off the event loop.
        body = await asyncio.to_thread(json.loads, raw)
        if not isinstance(body, dict):
            raise TypeError("ESPN injury report was not an object")
        return parse_injuries(body)
