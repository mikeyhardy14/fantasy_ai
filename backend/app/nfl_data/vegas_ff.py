"""Vegas team totals split by each player's earlier games.

The coefficients were fit on 2020-2025 NFL data. History lists are previous
games only, oldest first, and never include the game being projected. A missing
value is None and is skipped. This module does not invent routes, practice
reports, or end-zone targets.
"""

import math
import random

from app.nfl_data.base import PlayerProjection

SCORING = {
    "pass_yd": 0.04,
    "pass_td": 4.0,
    "int": -2.0,
    "rush_yd": 0.1,
    "rec_yd": 0.1,
    "td": 6.0,
    "rec": 1.0,
    "two_pt": 2.0,
    "fum_lost": -2.0,
}

TEAM_COEF = {
    "pass_att": (6.0938, 0.4928, -0.2499, 0.4854),
    "completions": (1.9288, 0.4299, -0.1536, 0.4611),
    "pass_yds": (12.4438, 7.6694, -2.0199, 0.2191),
    "pass_td": (-0.8608, 0.0937, -0.0129, 0.1625),
    "ints": (0.6854, 0.0025, -0.0150, 0.0242),
    "rush_att": (22.2238, -0.2413, 0.2994, 0.3758),
    "rush_yds": (67.3931, 0.0155, 1.1770, 0.4224),
    "rush_td": (0.0018, 0.0334, 0.0079, 0.1852),
}
TEAM_TRAIL_ALPHA = 0.25

SHARES = {
    "pass_att": ("pass_att", 0.70),
    "pass_yds": ("pass_yds", 0.80),
    "pass_td": ("pass_td", 0.90),
    "ints": ("ints", 0.90),
    "rush_att": ("rush_att", 0.70),
    "rush_yds": ("rush_yds", 0.80),
    "rush_td": ("rush_td", 0.92),
    "rec": ("completions", 0.70),
    "rec_yds": ("pass_yds", 0.80),
    "rec_td": ("pass_td", 0.92),
}

PRIORS = {
    "WR": {"tprr": 0.1997, "ypt": 8.1618, "cr": 0.6444, "tdt": 0.0505, "adot": 10.5444},
    "TE": {"tprr": 0.1691, "ypt": 7.4149, "cr": 0.7024, "tdt": 0.0538, "adot": 6.9166},
}
TGT_COEF = (0.0191, 0.3124, 0.7054, 0.2766, -0.0691, -0.0220)
REC_COEF = (-0.0162, 0.9944)
YDS_COEF = (-0.4052, 1.0165, -0.0248)
TD_COEF = (-0.00002, 0.6668, 0.28805, 0.03125)
PLAYER_EFFECT_K, PLAYER_EFFECT_W = 48, 0.5
NB_PHI, YPC_GAMMA_SHAPE = 0.078, 1.35

RB_RATIO_Q = [0, 1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 99, 100]
RB_RATIO_V = [
    -0.37, 0.0, 0.08, 0.19, 0.29, 0.37, 0.46, 0.54, 0.61, 0.68, 0.76, 0.83, 0.91,
    1.0, 1.09, 1.2, 1.33, 1.47, 1.64, 1.91, 2.31, 3.31, 6.3,
]

KIND_QB, KIND_RB, KIND_REC = 1.0, 2.0, 3.0
SIMS = 10000


def scoring_from_league(settings: dict | None) -> dict[str, float]:
    """League scoring keys mapped onto the rates this model multiplies."""
    scoring = dict(SCORING)
    incoming = settings or {}
    aliases = {
        "pass_yd": "pass_yd",
        "pass_td": "pass_td",
        "int": "pass_int",
        "rush_yd": "rush_yd",
        "rec_yd": "rec_yd",
        "rec": "rec",
        "fum_lost": "fum_lost",
        "two_pt": "pass_2pt",
    }
    for dest, src in aliases.items():
        if incoming.get(src) is not None:
            scoring[dest] = float(incoming[src])
    touchdown = incoming.get("rec_td", incoming.get("rush_td"))
    if touchdown is not None:
        scoring["td"] = float(touchdown)
    return scoring


def ewma(values, alpha: float) -> float | None:
    """Exponentially weighted mean, oldest first, newest weighted most. None is skipped."""
    num = den = 0.0
    weight = 1.0
    for value in reversed(list(values)):
        if value is None or (isinstance(value, float) and math.isnan(value)):
            continue
        num += weight * float(value)
        den += weight
        weight *= 1 - alpha
    return num / den if den else None


def ratio_ewma(player_vals, team_vals, alpha: float) -> float:
    player = ewma(player_vals, alpha)
    team = ewma(team_vals, alpha)
    return (player / team) if (player is not None and team) else 0.0


def implied_totals(total: float, home_spread: float) -> dict[str, tuple[float, float]]:
    """home_spread as a sportsbook shows it (home -3 = home favored by 3)."""
    home_margin = -home_spread
    return {
        "home": ((total + home_margin) / 2, home_margin),
        "away": ((total - home_margin) / 2, -home_margin),
    }


def team_projection(implied: float, margin: float, team_history: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for stat, (c0, c1, c2, c3) in TEAM_COEF.items():
        trail = ewma(team_history.get(stat) or [], TEAM_TRAIL_ALPHA)
        out[stat] = max(0.0, c0 + c1 * implied + c2 * margin + c3 * (trail if trail is not None else 0))
    return out


def share_projection(player_hist: list[dict], team_proj: dict[str, float]) -> dict[str, float]:
    proj: dict[str, float] = {}
    for stat, (team_stat, decay) in SHARES.items():
        share = ratio_ewma(
            [game.get(stat) for game in player_hist],
            [game.get("team_" + team_stat) for game in player_hist],
            1 - decay,
        )
        proj[stat] = share * team_proj[team_stat]
    fumbles = ewma([game.get("fum_lost", 0) for game in player_hist], 0.05)
    twos = ewma([game.get("two_pt", 0) for game in player_hist], 0.05)
    proj["fum_lost"] = fumbles or 0.0
    proj["two_pt"] = twos or 0.0
    return proj


def fantasy_points(stats: dict, scoring: dict | None = None) -> float:
    rates = scoring or SCORING
    return (
        rates["pass_yd"] * stats.get("pass_yds", 0)
        + rates["pass_td"] * stats.get("pass_td", 0)
        + rates["int"] * stats.get("ints", 0)
        + rates["rush_yd"] * stats.get("rush_yds", 0)
        + rates["rec_yd"] * stats.get("rec_yds", 0)
        + rates["td"] * (stats.get("rush_td", 0) + stats.get("rec_td", 0))
        + rates["rec"] * stats.get("rec", 0)
        + rates["two_pt"] * stats.get("two_pt", 0)
        + rates["fum_lost"] * stats.get("fum_lost", 0)
    )


def receiver_projection(
    pos: str,
    hist: list[dict],
    team_proj: dict[str, float],
    teammates_out_share: float = 0.0,
    questionable: bool = False,
    limited_practice: bool = False,
    model_residuals: list[float] | None = None,
    base: dict | None = None,
    scoring: dict | None = None,
) -> dict[str, float]:
    rates = scoring or SCORING
    prior = PRIORS[pos]
    pass_att = team_proj["pass_att"]
    pass_td = team_proj["pass_td"]

    target_share = ratio_ewma([game["targets"] for game in hist], [game["team_targets"] for game in hist], 0.3)
    route_vals = [
        (game["routes"] / game["team_dropbacks"])
        if game.get("routes") is not None and game.get("team_dropbacks")
        else game.get("snap_pct")
        for game in hist
    ]
    routes = min(ewma(route_vals, 0.3) or 0.0, 1.0)

    last = hist[-40:]
    targets_40 = sum(game["targets"] for game in last)
    routes_40 = sum(
        game["routes"]
        if game.get("routes") is not None
        else (game.get("snap_pct") or 0) * (game.get("team_dropbacks") or 0)
        for game in last
    )
    tprr = (targets_40 + 100 * prior["tprr"]) / (routes_40 + 100)
    yards_per_target = (sum(game["rec_yds"] for game in last) + 60 * prior["ypt"]) / (targets_40 + 60)
    catch_rate = (sum(game["rec"] for game in last) + 60 * prior["cr"]) / (targets_40 + 60)
    adot = (sum(game["air_yards"] for game in last) + 60 * prior["adot"]) / (targets_40 + 60)
    td_per_target = (sum(game["rec_td"] for game in last) + 150 * prior["tdt"]) / (targets_40 + 150)
    red_zone = ratio_ewma(
        [game["rz_targets"] for game in hist], [game["team_rz_targets"] for game in hist], 0.1
    ) or target_share
    end_zone = ratio_ewma(
        [game["ez_targets"] for game in hist], [game["team_ez_targets"] for game in hist], 0.1
    ) or target_share

    vacancy = teammates_out_share / max(1 - teammates_out_share, 0.3)
    coef = TGT_COEF
    targets = max(
        0.0,
        coef[0]
        + coef[1] * pass_att * target_share
        + coef[2] * pass_att * routes * tprr
        + coef[3] * pass_att * target_share * vacancy
        + coef[4] * pass_att * target_share * questionable
        + coef[5] * pass_att * target_share * limited_practice,
    )
    receptions = max(0.0, REC_COEF[0] + REC_COEF[1] * targets * catch_rate)
    yards = max(0.0, YDS_COEF[0] + YDS_COEF[1] * targets * yards_per_target + YDS_COEF[2] * targets * adot)
    touchdowns = max(
        0.005,
        TD_COEF[0] + TD_COEF[1] * targets * td_per_target + TD_COEF[2] * pass_td * red_zone + TD_COEF[3] * pass_td * end_zone,
    )

    rushing = base or {}
    extra = (
        rates["rush_yd"] * rushing.get("rush_yds", 0)
        + rates["td"] * rushing.get("rush_td", 0)
        + rates["two_pt"] * rushing.get("two_pt", 0)
        + rates["fum_lost"] * rushing.get("fum_lost", 0)
    )
    residuals = (model_residuals or [])[-32:]
    extra += PLAYER_EFFECT_W * sum(residuals) / (len(residuals) + PLAYER_EFFECT_K)
    points = rates["rec"] * receptions + rates["rec_yd"] * yards + rates["td"] * touchdowns + extra
    return {
        "targets": targets,
        "rec": receptions,
        "rec_yds": yards,
        "rec_td": touchdowns,
        "extra": extra,
        "points": points,
    }


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    limit = math.exp(-lam)
    count = 0
    product = 1.0
    while product > limit:
        count += 1
        product *= rng.random()
    return count - 1


def _binomial(rng: random.Random, trials: int, probability: float) -> int:
    if trials <= 0 or probability <= 0:
        return 0
    if probability >= 1:
        return trials
    return sum(1 for _ in range(trials) if rng.random() < probability)


def _interp(x: float, knots: list[float], values: list[float]) -> float:
    if x <= knots[0]:
        return values[0]
    if x >= knots[-1]:
        return values[-1]
    for index in range(1, len(knots)):
        if x <= knots[index]:
            span = knots[index] - knots[index - 1]
            share = (x - knots[index - 1]) / span if span else 0.0
            return values[index - 1] + share * (values[index] - values[index - 1])
    return values[-1]


def simulate_receiver(proj: dict, n: int = SIMS, rng: random.Random | None = None, scoring: dict | None = None) -> list[float]:
    rates = scoring or SCORING
    rng = rng or random.Random()
    shape = 1 / NB_PHI
    targets_mean = max(float(proj["targets"]), 1e-6)
    catch = min(max(float(proj["rec"]) / max(float(proj["targets"]), 0.1), 0.05), 0.95)
    yards_per_catch = min(max(float(proj["rec_yds"]) / max(float(proj["rec"]), 0.1), 3), 25)
    td_rate = min(max(float(proj["rec_td"]) / max(float(proj["rec"]), 0.1), 0), 0.6)
    extra = float(proj["extra"])
    draws: list[float] = []
    for _ in range(n):
        lam = rng.gammavariate(shape, targets_mean / shape)
        targets = _poisson(rng, lam)
        receptions = _binomial(rng, targets, catch)
        if receptions > 0:
            yard_shape = max(YPC_GAMMA_SHAPE * receptions, 1e-9)
            yards = rng.gammavariate(yard_shape, yards_per_catch / YPC_GAMMA_SHAPE)
        else:
            yards = 0.0
        touchdowns = _binomial(rng, receptions, td_rate)
        draws.append(rates["rec"] * receptions + rates["rec_yd"] * yards + rates["td"] * touchdowns + extra)
    return draws


def simulate_qb(points: float, n: int = SIMS, rng: random.Random | None = None) -> list[float]:
    rng = rng or random.Random()
    mean = max(points, 1.0)
    sd = max(0.05, 1.5 * (8.32 - 0.026 * mean))
    shape = (mean / sd) ** 2
    scale = sd**2 / mean
    return [rng.gammavariate(shape, scale) for _ in range(n)]


def simulate_rb(points: float, n: int = SIMS, rng: random.Random | None = None) -> list[float]:
    rng = rng or random.Random()
    mean = max(points, 1.0)
    return [mean * _interp(rng.uniform(0, 100), RB_RATIO_Q, RB_RATIO_V) for _ in range(n)]


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    count = len(ordered)
    if count == 0:
        return 0.0
    mid = count // 2
    if count % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * (q / 100)
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def start_sit(sims_a, sims_b, name_a: str = "A", name_b: str = "B") -> dict:
    left = [float(value) for value in sims_a]
    right = [float(value) for value in sims_b]
    count = min(len(left), len(right))
    if count == 0:
        probability = 0.5
    else:
        wins = ties = 0
        for index in range(count):
            if left[index] > right[index]:
                wins += 1
            elif left[index] == right[index]:
                ties += 1
        probability = wins / count + 0.5 * ties / count
    if probability >= 0.5:
        pick, prob = name_a, probability
    else:
        pick, prob = name_b, 1 - probability
    if prob < 0.55:
        label = "coin flip"
    elif prob < 0.62:
        label = "lean"
    elif prob < 0.72:
        label = "start"
    else:
        label = "strong start"
    return {
        "start": pick,
        "win_prob": round(prob, 3),
        "confidence": label,
        "median": (round(_median(left), 1), round(_median(right), 1)),
        "floor_p10": (round(_percentile(left, 10), 1), round(_percentile(right, 10), 1)),
        "ceiling_p90": (round(_percentile(left, 90), 1), round(_percentile(right, 90), 1)),
    }


def sims_for(detail: dict, n: int = SIMS, rng: random.Random | None = None) -> list[float] | None:
    """Draw a points range from the projection detail stored on a player."""
    if detail.get("vegas_ff") != 1:
        return None
    kind = detail.get("kind")
    if kind == KIND_QB:
        return simulate_qb(float(detail.get("points") or 0), n=n, rng=rng)
    if kind == KIND_RB:
        return simulate_rb(float(detail.get("points") or 0), n=n, rng=rng)
    if kind == KIND_REC:
        return simulate_receiver(
            {
                "targets": detail.get("targets") or 0,
                "rec": detail.get("rec") or 0,
                "rec_yds": detail.get("rec_yds") or 0,
                "rec_td": detail.get("rec_td") or 0,
                "extra": detail.get("extra") or 0,
            },
            n=n,
            rng=rng,
            scoring={
                "rec": float(detail.get("score_rec", SCORING["rec"])),
                "rec_yd": float(detail.get("score_rec_yd", SCORING["rec_yd"])),
                "td": float(detail.get("score_td", SCORING["td"])),
            },
        )
    return None


def project_player(
    *,
    position: str,
    week: int,
    implied: float,
    margin: float,
    team_history: dict,
    player_games: list[dict],
    scoring: dict | None = None,
    teammates_out_share: float = 0.0,
    questionable: bool = False,
) -> PlayerProjection | None:
    """Mean points for one player. None when there is no earlier game to share."""
    if not player_games:
        return None
    rates = scoring or SCORING
    team = team_projection(implied, margin, team_history)
    pos = position.upper()
    if pos in {"QB", "RB"}:
        shared = share_projection(player_games, team)
        points = fantasy_points(shared, rates)
        kind = KIND_QB if pos == "QB" else KIND_RB
        components = {"targets": 0.0, "rec": 0.0, "rec_yds": 0.0, "rec_td": 0.0, "extra": 0.0}
    elif pos in {"WR", "TE"}:
        shared = share_projection(player_games, team)
        receiving = receiver_projection(
            pos,
            player_games,
            team,
            teammates_out_share=teammates_out_share,
            questionable=questionable,
            limited_practice=False,
            base=shared,
            scoring=rates,
        )
        points = receiving["points"]
        kind = KIND_REC
        components = receiving
    else:
        return None
    shown = round(points, 1)
    games = float(len(player_games))
    return PlayerProjection(
        week=week,
        points=shown,
        source="vegas",
        note=f"Vegas share from {int(games)} earlier games (implied {implied:.1f}, margin {margin:+.1f})",
        detail={
            "vegas_ff": 1.0,
            "kind": kind,
            "games": games,
            "implied_points": float(implied),
            "margin": float(margin),
            "points": float(points),
            "targets": float(components.get("targets") or 0),
            "rec": float(components.get("rec") or 0),
            "rec_yds": float(components.get("rec_yds") or 0),
            "rec_td": float(components.get("rec_td") or 0),
            "extra": float(components.get("extra") or 0),
            "score_rec": float(rates["rec"]),
            "score_rec_yd": float(rates["rec_yd"]),
            "score_td": float(rates["td"]),
        },
    )
