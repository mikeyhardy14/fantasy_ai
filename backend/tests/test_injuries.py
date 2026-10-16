"""ESPN's injury report overlays Sleeper's once-a-day labels."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
from httpx import Response

from app.nfl_data.injuries import (
    EspnInjuryClient,
    InjuryReport,
    apply_injury_reports,
    parse_injuries,
)
from tests.fixtures import sleeper as fx

NOW = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)


def _entry(espn_id, status, fantasy=None, *, date="2026-10-18T14:30Z", body="Ankle", via_link=False):
    athlete = {"displayName": f"Player {espn_id}"}
    if via_link:
        athlete["links"] = [{"href": f"https://www.espn.com/nfl/player/_/id/{espn_id}/player"}]
    else:
        athlete["id"] = espn_id
    details = {"type": body}
    if fantasy:
        details["fantasyStatus"] = {"abbreviation": fantasy}
    return {"status": status, "date": date, "athlete": athlete, "details": details, "shortComment": f"{espn_id} news"}


def _body(*entries):
    return {"injuries": [{"id": "1", "injuries": list(entries)}]}


def test_espn_designations_map_to_sleeper_labels():
    reports = parse_injuries(
        _body(
            _entry("1", "Questionable", "QUESTIONABLE"),
            _entry("2", "Out", "INACTIVE"),
            _entry("3", "Injured Reserve", "IR-R"),
            _entry("4", "Out", "PUP-R"),
            _entry("5", "Suspension"),
            _entry("6", "Doubtful", "DOUBTFUL", via_link=True),
        ),
        now=NOW,
    )
    assert {key: report.status for key, report in reports.items()} == {
        "1": "Questionable",
        "2": "Out",
        "3": "IR",
        "4": "PUP",
        "5": "Sus",
        "6": "Doubtful",
    }
    assert reports["1"].body_part == "Ankle"
    assert reports["1"].note == "1 news"


def test_recently_cleared_players_lose_their_label_but_old_clearances_do_not_count():
    reports = parse_injuries(
        _body(
            _entry("1", "Active", date="2026-10-17T20:00Z"),
            _entry("2", "Active", date="2026-09-01T20:00Z"),
            _entry("3", "Day-To-Day", "SOMETHING_NEW"),
        ),
        now=NOW,
    )
    assert reports["1"].status is None and reports["1"].body_part is None
    assert "2" not in reports
    assert "3" not in reports


def test_newest_entry_wins_for_a_player():
    reports = parse_injuries(
        _body(
            _entry("1", "Questionable", "QUESTIONABLE", date="2026-10-16T10:00Z"),
            _entry("1", "Out", "OUT", date="2026-10-18T13:00Z"),
            _entry("1", "Questionable", "QUESTIONABLE", date="2026-10-17T10:00Z"),
        ),
        now=NOW,
    )
    assert reports["1"].status == "Out"


def _person(status, extra, *, name="Some Player", team="KC", body=None):
    return SimpleNamespace(name=name, nfl_team=team, injury_status=status, injury_body_part=body, extra=extra)


def test_reports_overlay_only_players_espn_lists():
    listed = _person(None, {"espn_id": "10"})
    cleared = _person("Out", {"espn_id": 11}, body="Knee")
    unlisted = _person("Questionable", {"espn_id": "12"}, body="Hip")
    no_match = _person("Doubtful", {}, name="Nobody Listed")
    reports = {
        "10": InjuryReport(status="Out", body_part="Hamstring", note="ruled out", updated_at=NOW),
        "11": InjuryReport(status=None, body_part=None, note="cleared", updated_at=NOW),
    }
    changed = apply_injury_reports([listed, cleared, unlisted, no_match], reports)
    assert changed == 2
    assert (listed.injury_status, listed.injury_body_part) == ("Out", "Hamstring")
    assert listed.extra["injury_source"] == "espn" and listed.extra["injury_notes"] == "ruled out"
    assert (cleared.injury_status, cleared.injury_body_part) == (None, None)
    assert unlisted.injury_status == "Questionable"
    assert no_match.injury_status == "Doubtful"


def test_newer_sleeper_news_beats_an_older_espn_tag():
    sleeper_news_ms = (NOW - timedelta(hours=2)).timestamp() * 1000
    stale_espn = _person("Out", {"espn_id": "10", "news_updated": sleeper_news_ms})
    fresh_espn = _person("Questionable", {"espn_id": "11", "news_updated": sleeper_news_ms})
    reports = {
        "10": InjuryReport(status="Questionable", body_part=None, note=None, updated_at=NOW - timedelta(days=5)),
        "11": InjuryReport(status="Out", body_part=None, note="inactive", updated_at=NOW),
    }
    apply_injury_reports([stale_espn, fresh_espn], reports)
    assert stale_espn.injury_status == "Out"
    assert fresh_espn.injury_status == "Out"


def test_players_without_an_espn_id_match_by_name_and_team():
    reports = parse_injuries(
        _body(
            {**_entry("20", "Out", "OUT"), "athlete": {"id": "20", "displayName": "Marvin Harrison Jr.", "team": {"abbreviation": "ARI"}}},
            {**_entry("21", "Out", "OUT"), "athlete": {"id": "21", "displayName": "Cam Smith", "team": {"abbreviation": "WSH"}}},
            {**_entry("22", "Doubtful", "DOUBTFUL"), "athlete": {"id": "22", "displayName": "Cam Smith", "team": {"abbreviation": "WSH"}}},
        ),
        now=NOW,
    )
    harrison = _person(None, {}, name="Marvin Harrison", team="ARI")
    same_name_elsewhere = _person(None, {}, name="Marvin Harrison", team="KC")
    ambiguous = _person("Questionable", {}, name="Cam Smith", team="WAS")
    apply_injury_reports([harrison, same_name_elsewhere, ambiguous], reports)
    assert harrison.injury_status == "Out"
    assert same_name_elsewhere.injury_status is None
    assert ambiguous.injury_status == "Questionable"


async def test_client_caches_and_keeps_the_last_good_report_when_espn_fails():
    calls = {"n": 0, "fail": False}

    def handler(request):
        calls["n"] += 1
        if calls["fail"]:
            return Response(503)
        recent = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%MZ")
        return Response(200, json=_body(_entry("1", "Out", "OUT", date=recent)))

    client = EspnInjuryClient(
        "https://espn.test/injuries", ttl_seconds=600, retry_seconds=0, transport=httpx.MockTransport(handler)
    )
    first = await client.reports()
    assert first["1"].status == "Out"
    assert await client.reports() is first
    assert calls["n"] == 1

    client._next_fetch = 0
    calls["fail"] = True
    assert (await client.reports())["1"].status == "Out"
    assert calls["n"] == 2


class FakeInjuries:
    def __init__(self, reports):
        self._reports = reports

    async def reports(self):
        return self._reports


async def test_ai_management_acts_on_espn_news_without_anyone_opening_the_app(client, auth_headers, sleeper_mock, state):
    from app.services import live_league
    from app.services.lineup_management import sweep_lineup_management
    from tests.test_sleeper_lineup import TOKEN, _import, _save_token, install_graphql

    players = deepcopy(fx.PLAYERS)
    players["2001"]["espn_id"] = 9001
    sleeper_mock.get("/players/nfl").mock(return_value=Response(200, json=players))
    install_graphql(sleeper_mock, {})
    league = await _import(client, auth_headers)
    await _save_token(client, auth_headers, TOKEN)
    saved = await client.put(f"/api/leagues/{league['id']}/management", json={"enabled": True}, headers=auth_headers)
    assert saved.status_code == 200, saved.text
    await live_league.drain_background()

    # Sleeper still lists Dash Ground as healthy; ESPN has him inactive.
    state.injuries = FakeInjuries({"9001": InjuryReport(status="Out", body_part="Ankle", note="inactive", updated_at=NOW)})
    live_league._fresh.clear()

    seen: list[str] = []

    async def apply(_league, move):
        seen.append(move.summary)
        return "saved"

    summaries = await sweep_lineup_management(state, apply=apply)
    assert any("Flash Backup" in summary and "Dash Ground" in summary for summary in summaries)

    live_league.mark_fresh(league["id"])
    team = (await client.get(f"/api/leagues/{league['id']}/team", headers=auth_headers)).json()
    dash = next(slot for slot in team["starters"] if slot["player"] and slot["player"]["name"] == "Dash Ground")
    assert dash["player"]["injury_status"] == "Out"
    assert "OUT" in dash["flags"]
