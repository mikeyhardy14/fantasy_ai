"""Season totals from scored weeks should not be reported as missing."""

from types import SimpleNamespace

from app.ai.fallback import omit_false_season_gap
from app.ai.tools.league_tools import season_stats_for_player
from app.nfl_data.base import PlayerSeasonStats
from app.schemas.ai import TeamAnalysis, TradeStrategy


def test_sleeper_season_points_stand_in_for_a_missing_file():
    player = SimpleNamespace(season_points=40.8, points_per_game=20.4)
    stats = season_stats_for_player(None, player, 2026)
    assert stats is not None
    assert stats.fantasy_points == 40.8
    assert stats.games_played == 2
    assert stats.source == "sleeper"


def test_saved_season_line_is_kept():
    saved = PlayerSeasonStats(season=2026, games_played=3, fantasy_points=55.2)
    stats = season_stats_for_player(saved, SimpleNamespace(season_points=1.0, points_per_game=1.0), 2026)
    assert stats.games_played == 3
    assert stats.fantasy_points == 55.2


def test_analysis_drops_a_false_season_gap_when_totals_exist():
    analysis = TeamAnalysis(
        team_summary="Ready.",
        strengths=["Depth"],
        weaknesses=["Bye"],
        lineup_changes=[],
        waiver_priorities=[],
        trade_strategy=TradeStrategy(can_trade_away=[], should_target=[], reasoning="Hold."),
        this_week=["Confirm the lineup."],
        data_gaps=[
            "Season-long cumulative scoring stats are unavailable (points display as null).",
            "Bye weeks unknown.",
        ],
    )
    roster = SimpleNamespace(all_roster=[SimpleNamespace(player=SimpleNamespace(season_points=40.8))])
    cleaned = omit_false_season_gap(analysis, roster)
    assert cleaned.data_gaps == ["Bye weeks unknown."]
