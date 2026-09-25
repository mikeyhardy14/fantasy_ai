"""Weekly player ranks from the posted line and this league's roster.

Points are the Vegas usage model when the player has earlier games, otherwise a
saved projection or the DraftKings prop. Value is those points minus the
replacement starter. Players on bye or ruled out are left off.
"""

from dataclasses import dataclass

_OUT = {"OUT", "IR", "PUP", "SUS", "SUSPENDED"}
_NON_LINEUP = {"BN", "IR", "TAXI"}
LIMIT = 80
MATCH_LIMIT = 200


@dataclass
class RankCandidate:
    player_id: str
    name: str
    position: str | None
    nfl_team: str | None
    opponent: str | None
    home: bool | None
    headshot_url: str | None
    injury_status: str | None
    on_bye: bool
    ruled_out: bool
    total: float | None
    spread: float | None
    implied_points: float | None
    win_probability: float | None
    book_count: int
    books: list[str]
    projected_points: float | None
    projection_source: str | None
    season_points: float | None = None


@dataclass
class RankedPlayer:
    rank: int
    vorp: float | None
    player: RankCandidate


def ruled_out(status: str | None) -> bool:
    if not status:
        return False
    return status.strip().upper() in _OUT


def replacement_ranks(team_count: int, roster_positions: list[str]) -> dict[str, int]:
    """How many starters the league needs at each position.

    A flex spot is split between RB and WR. A rec flex is split between WR and TE.
    A superflex counts as another quarterback slot.
    """
    if team_count <= 0:
        return {}
    starters = [slot for slot in roster_positions if slot not in _NON_LINEUP]
    flex = starters.count("FLEX") + starters.count("WRRB_FLEX")
    rec = starters.count("REC_FLEX")
    specs = {
        "QB": starters.count("QB") + starters.count("SUPER_FLEX"),
        "RB": starters.count("RB") + flex / 2,
        "WR": starters.count("WR") + flex / 2 + rec / 2,
        "TE": starters.count("TE") + rec / 2,
        "K": starters.count("K"),
        "DEF": starters.count("DEF") + starters.count("DST"),
    }
    ranks: dict[str, int] = {}
    for pos, slots in specs.items():
        if slots <= 0:
            continue
        ranks[pos] = max(1, int(round(slots * team_count)))
    return ranks


def build_rankings(
    players: list[RankCandidate],
    *,
    team_count: int,
    roster_positions: list[str],
    position: str | None = None,
    query: str | None = None,
    nfl_team: str | None = None,
    only_ids: set[str] | None = None,
    exclude_ids: set[str] | None = None,
) -> tuple[list[RankedPlayer], bool]:
    eligible = [
        player
        for player in players
        if player.projected_points is not None and not player.on_bye and not player.ruled_out
    ]
    if position == "FLEX":
        eligible = [player for player in eligible if player.position in {"RB", "WR", "TE"}]
    elif position:
        eligible = [player for player in eligible if player.position == position]
    ranks = replacement_ranks(team_count, roster_positions)
    by_pos: dict[str, list[RankCandidate]] = {}
    for player in eligible:
        if player.position:
            by_pos.setdefault(player.position, []).append(player)
    vorp: dict[str, float] = {}
    for pos, group in by_pos.items():
        need = ranks.get(pos)
        if need is None or len(group) < need:
            continue
        ordered = sorted(group, key=lambda player: (-(player.projected_points or 0), player.name))
        baseline = ordered[need - 1].projected_points or 0
        for player in ordered:
            vorp[player.player_id] = round((player.projected_points or 0) - baseline, 1)
    ordered = sorted(
        eligible,
        key=lambda player: (
            player.player_id not in vorp,
            -(vorp.get(player.player_id) or 0),
            -(player.projected_points or 0),
            player.name,
        ),
    )
    ranked = [
        RankedPlayer(rank=index + 1, vorp=vorp.get(player.player_id), player=player)
        for index, player in enumerate(ordered)
    ]
    needle = " ".join(query.casefold().split()) if query else ""
    if len(needle) >= 2:
        ranked = [row for row in ranked if needle in row.player.name.casefold()]
    if nfl_team:
        code = nfl_team.strip().upper()
        ranked = [row for row in ranked if (row.player.nfl_team or "").upper() == code]
    if only_ids is not None:
        ranked = [row for row in ranked if row.player.player_id in only_ids]
    if exclude_ids:
        ranked = [row for row in ranked if row.player.player_id not in exclude_ids]
    narrowing = len(needle) >= 2 or bool(nfl_team) or only_ids is not None or bool(exclude_ids)
    cap = MATCH_LIMIT if narrowing else LIMIT
    return ranked[:cap], len(ranked) > cap
