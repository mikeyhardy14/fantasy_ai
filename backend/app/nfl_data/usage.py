"""Earlier-game logs for the Vegas share model, from Sleeper weekly stats.

Team totals are the sum of players currently on that team. Only weeks before
the projected week are included. A counting stat missing from a played game is
zero. Routes and end-zone targets are not in this feed, so those fields stay
None and the model falls back to snap share and target share.
"""

from dataclasses import dataclass, field

_PLAYED = ("pass_att", "rush_att", "rec_tgt", "rec", "off_snp", "pass_yd", "rush_yd", "rec_yd")
_TEAM_FROM = {
    "pass_att": "pass_att",
    "pass_cmp": "completions",
    "pass_yd": "pass_yds",
    "pass_td": "pass_td",
    "pass_int": "ints",
    "rush_att": "rush_att",
    "rush_yd": "rush_yds",
    "rush_td": "rush_td",
    "rec_tgt": "targets",
    "rec_rz_tgt": "rz_targets",
}
_TEAM_STATS = (
    "pass_att",
    "completions",
    "pass_yds",
    "pass_td",
    "ints",
    "rush_att",
    "rush_yds",
    "rush_td",
    "targets",
    "rz_targets",
    "ez_targets",
)
_OUT = {"OUT", "DOUBTFUL"}


def _num(row: dict, key: str) -> float | None:
    if key not in row or row[key] is None:
        return None
    try:
        return float(row[key])
    except (TypeError, ValueError):
        return None


def _played(row: dict) -> bool:
    return any((_num(row, key) or 0) > 0 for key in _PLAYED)


@dataclass
class UsageTable:
    team_history: dict[str, dict[str, list[float | None]]] = field(default_factory=dict)
    team_weeks: dict[str, list[int]] = field(default_factory=dict)
    games: dict[str, list[dict]] = field(default_factory=dict)
    teams: dict[str, str] = field(default_factory=dict)
    injuries: dict[str, str | None] = field(default_factory=dict)
    positions: dict[str, str | None] = field(default_factory=dict)

    def out_share(self, team: str, sleeper_id: str) -> float:
        """Trailing target share of Out or Doubtful teammates who played recently."""
        from app.nfl_data.vegas_ff import ratio_ewma

        recent = set((self.team_weeks.get(team) or [])[-3:])
        if not recent:
            return 0.0
        total = 0.0
        for other, games in self.games.items():
            if other == sleeper_id or self.teams.get(other) != team:
                continue
            position = (self.positions.get(other) or "").upper()
            if position not in {"WR", "TE", "RB"}:
                continue
            status = (self.injuries.get(other) or "").strip().upper()
            if status not in _OUT:
                continue
            if not any(game.get("_week") in recent for game in games):
                continue
            total += ratio_ewma(
                [game.get("targets") for game in games],
                [game.get("team_targets") for game in games],
                0.3,
            )
        return total


def build_usage(
    weeks: list[tuple[int, dict]],
    teams: dict[str, str],
    injuries: dict[str, str | None],
    positions: dict[str, str | None],
) -> UsageTable:
    """weeks is (week number, sleeper id -> stat row), oldest first."""
    table = UsageTable(teams=dict(teams), injuries=dict(injuries), positions=dict(positions))
    history: dict[str, dict[str, list[float | None]]] = {}
    team_weeks: dict[str, list[int]] = {}
    pending: dict[str, list[dict]] = {}

    for week, blob in weeks:
        if not isinstance(blob, dict):
            continue
        sums: dict[str, dict[str, float]] = {}
        seen: dict[str, set[str]] = {}
        rows: list[tuple[str, str, dict]] = []
        for sleeper_id, row in blob.items():
            team = teams.get(str(sleeper_id))
            if not team or not isinstance(row, dict) or not _played(row):
                continue
            bucket = sums.setdefault(team, {})
            marks = seen.setdefault(team, set())
            for src, dest in _TEAM_FROM.items():
                value = _num(row, src)
                if value is None:
                    continue
                bucket[dest] = bucket.get(dest, 0.0) + value
                marks.add(dest)
            rows.append((str(sleeper_id), team, row))
        for team, marks in seen.items():
            week_totals = {stat: (sums[team][stat] if stat in marks else None) for stat in _TEAM_STATS}
            # End-zone targets are not published, so the team total stays missing.
            week_totals["ez_targets"] = None
            hist = history.setdefault(team, {stat: [] for stat in _TEAM_STATS})
            for stat in _TEAM_STATS:
                hist[stat].append(week_totals[stat])
            team_weeks.setdefault(team, []).append(week)
            for sleeper_id, row_team, row in rows:
                if row_team != team:
                    continue
                pending.setdefault(sleeper_id, []).append(_game(week, row, week_totals))

    table.team_history = history
    table.team_weeks = team_weeks
    table.games = pending
    return table


def _game(week: int, row: dict, team_totals: dict[str, float | None]) -> dict:
    def zero(key: str) -> float:
        return _num(row, key) or 0.0

    snaps = _num(row, "off_snp")
    team_snaps = _num(row, "tm_off_snp")
    snap_pct = snaps / team_snaps if snaps is not None and team_snaps else None
    twos = [_num(row, key) for key in ("pass_2pt", "rush_2pt", "rec_2pt")]
    two_pt = sum(value for value in twos if value is not None)
    dropbacks = team_totals.get("pass_att")
    return {
        "_week": week,
        "pass_att": zero("pass_att"),
        "pass_yds": zero("pass_yd"),
        "pass_td": zero("pass_td"),
        "ints": zero("pass_int"),
        "rush_att": zero("rush_att"),
        "rush_yds": zero("rush_yd"),
        "rush_td": zero("rush_td"),
        "rec": zero("rec"),
        "rec_yds": zero("rec_yd"),
        "rec_td": zero("rec_td"),
        "fum_lost": zero("fum_lost"),
        "two_pt": two_pt,
        "team_pass_att": team_totals.get("pass_att"),
        "team_completions": team_totals.get("completions"),
        "team_pass_yds": team_totals.get("pass_yds"),
        "team_pass_td": team_totals.get("pass_td"),
        "team_ints": team_totals.get("ints"),
        "team_rush_att": team_totals.get("rush_att"),
        "team_rush_yds": team_totals.get("rush_yds"),
        "team_rush_td": team_totals.get("rush_td"),
        "targets": zero("rec_tgt"),
        "team_targets": team_totals.get("targets"),
        "routes": None,
        "team_dropbacks": dropbacks,
        "snap_pct": snap_pct,
        "air_yards": zero("rec_air_yd"),
        "rz_targets": zero("rec_rz_tgt"),
        "team_rz_targets": team_totals.get("rz_targets"),
        "ez_targets": None,
        "team_ez_targets": None,
    }
