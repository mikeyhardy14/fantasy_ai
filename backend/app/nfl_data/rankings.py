"""Weekly player ranks from the posted line and this league's roster.

Points are the player's share of the implied team total (or a saved projection
when one is stored). Value is those points minus the replacement starter.
Players on bye or ruled out are left off. Play volume, usage shares, props,
and floor/ceiling simulations are not applied.
"""

from dataclasses import dataclass

_OUT = {"OUT", "IR", "PUP", "SUS", "SUSPENDED"}
_ORDER = ("QB", "RB", "WR", "TE", "K", "DEF")
_NON_LINEUP = {"BN", "IR", "TAXI"}
LIMIT = 80


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


def replacement_sentence(team_count: int, roster_positions: list[str]) -> str | None:
    ranks = replacement_ranks(team_count, roster_positions)
    if not ranks:
        return None
    listed = ", ".join(f"{pos}{ranks[pos]}" for pos in _ORDER if pos in ranks)
    starters = [slot for slot in roster_positions if slot not in _NON_LINEUP]
    flex = starters.count("FLEX") + starters.count("WRRB_FLEX")
    flex_note = " Flex spots are split between RB and WR." if flex else ""
    return (
        f"Value is projected points minus the replacement starter in this {team_count}-team league: "
        f"{listed}.{flex_note}"
    )


def ranking_notes(
    players: list[RankCandidate],
    *,
    team_count: int,
    roster_positions: list[str],
    truncated: bool,
) -> list[str]:
    ranked = [player for player in players if player.projected_points is not None and not player.on_bye and not player.ruled_out]
    books: list[str] = []
    max_books = 0
    sources: set[str] = set()
    for player in ranked:
        max_books = max(max_books, player.book_count)
        for name in player.books:
            if name not in books:
                books.append(name)
        if player.projection_source and player.projection_source != "vegas":
            sources.add(player.projection_source)
    notes: list[str] = []
    if max_books <= 1:
        label = ", ".join(books) if books else "one posted line"
        notes.append(
            f"Implied team points use {label}. One line is posted per game, so this is not an average of several books. "
            "Home points are (total − home spread) / 2."
        )
    else:
        notes.append(
            f"Implied team points average {max_books} books ({', '.join(books)}). "
            "Home points are (total − home spread) / 2."
        )
    notes.append(
        "Projected points are the DraftKings prop lines times this league's scoring. A player with no posted prop has no projection."
    )
    if sources:
        listed = ", ".join(sorted(sources))
        notes.append(f"Where a saved projection exists ({listed}), that number is used instead of the prop lines.")
    notes.append("Win probability removes the vig from the moneyline when both prices are posted.")
    sentence = replacement_sentence(team_count, roster_positions)
    if sentence:
        notes.append(sentence)
    short = [
        player
        for player in ranked
        if player.position in replacement_ranks(team_count, roster_positions)
        and _pool_short(player.position, ranked, replacement_ranks(team_count, roster_positions))
    ]
    if short:
        notes.append("Value is blank where fewer players are in this pool than the replacement rank.")
    notes.append("Players on bye or ruled out are left off.")
    notes.append(
        "Team play counts, recent usage shares, and floor and ceiling simulations are not in these ranks."
    )
    if truncated:
        notes.append(f"Showing the top {LIMIT}.")
    return notes


def _pool_short(position: str | None, players: list[RankCandidate], ranks: dict[str, int]) -> bool:
    if not position or position not in ranks:
        return False
    count = sum(1 for player in players if player.position == position and player.projected_points is not None)
    return count < ranks[position]


def build_rankings(
    players: list[RankCandidate],
    *,
    team_count: int,
    roster_positions: list[str],
    position: str | None = None,
) -> tuple[list[RankedPlayer], list[str]]:
    eligible = [
        player
        for player in players
        if player.projected_points is not None and not player.on_bye and not player.ruled_out
    ]
    if position:
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
    truncated = len(ordered) > LIMIT
    shown = ordered[:LIMIT]
    notes = ranking_notes(players, team_count=team_count, roster_positions=roster_positions, truncated=truncated)
    return [RankedPlayer(rank=index + 1, vorp=vorp.get(player.player_id), player=player) for index, player in enumerate(shown)], notes
