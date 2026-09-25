"""Turn a posted total and spread into a fantasy projection.

This does not invent player stats. It splits the Vegas implied team total by a
fixed depth-chart weight, then nudges that share for the league's scoring
settings. No line means no projection.

Weights are fantasy points per implied team point in full PPR with 4-point
passing touchdowns. A 24-point implied total is about 17 for the QB1 and 14
for the RB1. Unknown depth is treated as the starter for QB and K, and as the
second option for RB, WR, and TE, so a missing depth chart is not assumed to
be the starter.
"""

from app.nfl_data.base import PlayerProjection

# (position, depth) -> share of the team's implied points.
_WEIGHTS: dict[tuple[str, int], float] = {
    ("QB", 1): 0.72,
    ("QB", 2): 0.06,
    ("RB", 1): 0.58,
    ("RB", 2): 0.36,
    ("RB", 3): 0.12,
    ("WR", 1): 0.55,
    ("WR", 2): 0.42,
    ("WR", 3): 0.28,
    ("WR", 4): 0.12,
    ("TE", 1): 0.34,
    ("TE", 2): 0.10,
    ("K", 1): 0.33,
    ("K", 2): 0.04,
}

_DEPTH_CAP = {"QB": 2, "RB": 3, "WR": 4, "TE": 2, "K": 2, "DEF": 1}


def implied_team_points(total: float, spread: float) -> float:
    """Team points implied by the total and this team's spread.

    Spread is from this team's side: negative means favored. A 47.5 total and
    a -3.5 spread implies 25.5; the dog at +3.5 implies 22.0.
    """
    return (total - spread) / 2


def normalize_position(position: str | None) -> str | None:
    if not position:
        return None
    pos = position.upper()
    if pos in {"DST", "D/ST", "D"}:
        return "DEF"
    if pos == "PK":
        return "K"
    return pos


def depth_from_extra(extra: dict | None) -> int | None:
    if not extra:
        return None
    raw = extra.get("depth_chart_order")
    if raw is None or raw == "":
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _effective_depth(position: str, depth: int | None) -> int:
    if depth is None or depth < 1:
        return 1 if position in {"QB", "K", "DEF"} else 2
    return min(depth, _DEPTH_CAP.get(position, 1))


def _scoring_multiplier(position: str, scoring: dict) -> float:
    try:
        rec = float(scoring.get("rec", 0) or 0)
    except (TypeError, ValueError):
        rec = 0.0
    try:
        pass_td = float(scoring.get("pass_td", 4) or 4)
    except (TypeError, ValueError):
        pass_td = 4.0
    if position == "QB":
        return 1.15 if pass_td >= 6 else 1.0
    if rec >= 1:
        return 1.0
    if rec <= 0:
        return {"WR": 0.78, "TE": 0.82, "RB": 0.90}.get(position, 1.0)
    return {"WR": 0.90, "TE": 0.92, "RB": 0.95}.get(position, 1.0)


def project_from_line(
    *,
    week: int,
    position: str | None,
    depth: int | None,
    spread: float | None,
    total: float | None,
    implied: float | None,
    scoring: dict | None,
) -> PlayerProjection | None:
    """Fantasy points from one game's line. None when the line or role is missing."""
    pos = normalize_position(position)
    if pos is None or implied is None or total is None or spread is None:
        return None
    scoring = scoring or {}
    if pos == "DEF":
        opponent_implied = total - implied
        points = max(0.0, round(14 - 0.35 * opponent_implied, 1))
        return PlayerProjection(
            week=week,
            points=points,
            source="vegas",
            detail={
                "opponent_implied": round(opponent_implied, 2),
                "total": total,
                "spread": spread,
            },
            note=f"Vegas opp implied {opponent_implied:.1f} (O/U {total:g}, spread {spread:+g})",
        )
    used_depth = _effective_depth(pos, depth)
    weight = _WEIGHTS.get((pos, used_depth))
    if weight is None:
        return None
    multiplier = _scoring_multiplier(pos, scoring)
    points = round(weight * multiplier * implied, 1)
    return PlayerProjection(
        week=week,
        points=points,
        source="vegas",
        detail={
            "implied_points": round(implied, 2),
            "spread": spread,
            "total": total,
            "weight": weight,
            "depth": float(used_depth),
            "depth_known": 1.0 if depth else 0.0,
            "multiplier": multiplier,
        },
        note=f"Vegas implied {implied:.1f} (O/U {total:g}, spread {spread:+g})",
    )


_ROLES = {
    ("QB", 1): "starting quarterback",
    ("QB", 2): "backup quarterback",
    ("RB", 1): "lead running back",
    ("RB", 2): "second running back",
    ("RB", 3): "third running back",
    ("WR", 1): "top receiver",
    ("WR", 2): "second receiver",
    ("WR", 3): "third receiver",
    ("WR", 4): "fourth receiver",
    ("TE", 1): "starting tight end",
    ("TE", 2): "backup tight end",
    ("K", 1): "kicker",
    ("K", 2): "backup kicker",
}


def _american(ml: float) -> str:
    number = int(round(ml))
    return f"+{number}" if number > 0 else str(number)


def explain_projection(
    projection: PlayerProjection | None,
    *,
    on_bye: bool,
    opponent: str | None,
    team: str | None,
    position: str | None,
) -> list[str]:
    """Plain sentences for the number on the roster. No extra prediction."""
    club = team or "This team"
    if projection is None:
        if on_bye:
            return [f"No projection. {club} is on bye."]
        return [
            "No projection. There is no earlier game to apply the Vegas total, and no posted prop line for this player."
        ]
    if projection.source == "sleeper":
        return [f"{projection.points:g} is Sleeper's projected points for this week."]
    if projection.source != "vegas":
        return [
            f"{projection.points:g} is a saved projection ({projection.source}).",
            "It is not calculated from this week's prop lines.",
        ]
    detail = projection.detail
    if detail.get("props") == 1:
        lines = [
            f"{projection.points:g} adds up the DraftKings lines using this league's scoring.",
            "Rushing yards, receiving yards, receptions, and passing yards use the posted total.",
        ]
        if detail.get("any_td_p") and detail.get("any_td_ml") is not None:
            lam = detail.get("rush_td") if detail.get("any_on_rush") == 1 else detail.get("rec_td")
            if lam is not None:
                lines.append(
                    f"Anytime TD {_american(detail['any_td_ml'])} is a {detail['any_td_p']:.0%} price. "
                    f"Expected touchdowns are {lam:.2f}."
                )
        if detail.get("pass_td_p") is not None and "pass_td" in detail:
            minimum = int(detail.get("pass_td_min") or 1)
            lines.append(
                f"Passing touchdowns over {detail['pass_td_ou']:g} at {_american(detail['pass_td_over'])} / {_american(detail['pass_td_under'])} "
                f"is a {detail['pass_td_p']:.0%} chance of {minimum} or more after the vig is removed. "
                f"Expected passing touchdowns are {detail['pass_td']:.2f}."
            )
        if detail.get("pass_int_p") is not None and "pass_int" in detail:
            minimum = int(detail.get("pass_int_min") or 1)
            lines.append(
                f"Interceptions over {detail['pass_int_ou']:g} at {_american(detail['pass_int_over'])} / {_american(detail['pass_int_under'])} "
                f"is a {detail['pass_int_p']:.0%} chance of {minimum} or more after the vig is removed. "
                f"Expected interceptions are {detail['pass_int']:.2f}."
            )
        return lines
    if detail.get("vegas_ff") == 1:
        games = int(detail.get("games") or 0)
        implied = detail.get("implied_points")
        margin = detail.get("margin")
        game_word = "game" if games == 1 else "games"
        lines = [
            f"{projection.points:g} is this player's share of the points Vegas implies for {club}.",
            f"{club} is implied for {implied:g} points, with an expected margin of {margin:+g}.",
            f"The share uses {games} earlier {game_word} this season. The game being projected is not included.",
        ]
        if detail.get("kind") == 3:
            lines.append(
                "Targets, yards, and touchdowns shrink toward the position average. "
                "Route counts and end-zone targets are not in the stat feed, so those pieces use snap share and target share."
            )
        return lines
    if "opponent_implied" in detail:
        opp = detail["opponent_implied"]
        foe = f" against {opponent}" if opponent else ""
        return [
            f"{projection.points:g} is a defense projection from the Vegas total.",
            f"The opponent{foe} is implied for {opp:g} points (total {detail['total']:g}, spread {detail['spread']:+g}).",
            f"Defense points are 14 minus 0.35 times that implied total, and the result is not allowed to go below zero.",
            f"14 − 0.35 × {opp:g} = {projection.points:g}.",
        ]
    if "weight" not in detail or "implied_points" not in detail:
        return [projection.note or f"{projection.points:g} comes from the Vegas line."]
    implied = detail["implied_points"]
    weight = detail["weight"]
    multiplier = detail.get("multiplier", 1.0)
    depth = int(detail.get("depth") or 1)
    pos = normalize_position(position) or (position or "").upper()
    role = _ROLES.get((pos, depth), f"depth {depth} {pos or 'player'}".strip())
    foe = f" against {opponent}" if opponent else ""
    lines = [
        f"{projection.points:g} is this player's share of the points Vegas implies for {club}.",
        f"{club}{foe} is implied for {implied:g} points (spread {detail['spread']:+g}, total {detail['total']:g}).",
        f"The split treats this player as the {role}, which is {weight:.0%} of that team total.",
    ]
    if detail.get("depth_known") == 0 and pos not in {"QB", "K", "DEF"}:
        lines.append("No depth-chart order is stored, so this uses the second option at the position instead of assuming the starter.")
    if multiplier != 1:
        lines.append(f"This league's reception and passing-touchdown settings multiply that share by {multiplier:g}.")
    lines.append(f"{weight:.0%} × {multiplier:g} × {implied:g} = {projection.points:g}.")
    return lines
