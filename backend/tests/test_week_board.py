"""NFL scoreboard loads for weeks other than the league's current week."""

from types import SimpleNamespace

from app.nfl_data.espn import GameSummary
from datetime import datetime, timezone

from app.nfl_data.week import board_week
from app.services.league_context import LeagueContextService, _matchup_status


class FakeNfl:
    name = "fake"

    def __init__(self):
        self.requested: list[tuple[int, int]] = []

    async def live_summaries(self, season: int, week: int):
        self.requested.append((season, week))
        return [
            GameSummary(
                away="BUF" if week == 3 else "SF",
                home="KC",
                away_score=17 if week == 3 else None,
                home_score=24 if week == 3 else None,
                state="post" if week == 3 else "pre",
                detail="Final" if week == 3 else "Sun 1:00 PM",
                summary=None,
                broadcast="CBS",
            )
        ]


async def test_board_returns_nfl_games_for_a_past_week():
    nfl = FakeNfl()
    ctx = LeagueContextService(session=None, nfl_data=nfl)
    league = SimpleNamespace(season=2026, current_week=4)
    games, blob = await ctx._current_board(league, 3)
    assert nfl.requested == [(2026, 3)]
    assert blob == {}
    assert games[0].away == "BUF"
    assert games[0].home == "KC"
    assert games[0].state == "post"
    assert games[0].away_score == 17
    assert games[0].detail == "Final"


async def test_board_keeps_separate_slates_per_week():
    nfl = FakeNfl()
    ctx = LeagueContextService(session=None, nfl_data=nfl)
    league = SimpleNamespace(season=2026, current_week=4)
    past, _ = await ctx._current_board(league, 3)
    now, _ = await ctx._current_board(league, 4)
    assert past[0].away == "BUF" and past[0].state == "post"
    assert now[0].away == "SF" and now[0].state == "pre"
    assert nfl.requested == [(2026, 3), (2026, 4)]


def test_matchup_is_final_when_every_nfl_game_is_over():
    done = [SimpleNamespace(state="post"), SimpleNamespace(state="post")]
    live = [SimpleNamespace(state="post"), SimpleNamespace(state="in")]
    assert _matchup_status(4, 4, 110.0, 98.0, done) == "final"
    assert _matchup_status(4, 4, 110.0, 98.0, live) == "in_progress"
    assert _matchup_status(4, 4, 110.0, 98.0, []) == "in_progress"


def test_board_week_advances_on_tuesday_when_the_slate_is_final():
    tuesday = datetime(2026, 9, 29, 15, tzinfo=timezone.utc)
    monday = datetime(2026, 9, 28, 20, tzinfo=timezone.utc)
    assert board_week(4, slate_final=True, now=tuesday) == 5
    assert board_week(4, slate_final=True, now=monday) == 4
    assert board_week(4, slate_final=False, now=tuesday) == 4
