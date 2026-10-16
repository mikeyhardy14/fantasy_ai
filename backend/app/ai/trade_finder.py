"""Find trades where both teams gain starter PPG after an optimal lineup."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from uuid import UUID

from app.intelligence.lineup import is_eligible
from app.schemas.league import PlayerOut, RosterSlotOut, TeamOut


def player_ppg(player: PlayerOut | None) -> float | None:
    if player is None:
        return None
    if player.points_per_game is not None:
        return float(player.points_per_game)
    if player.projected_points is not None:
        return float(player.projected_points)
    return None


def optimal_starter_ppg(team: TeamOut) -> float | None:
    """Greedy best lineup using PPG (or week projection as a stand-in)."""
    pool = [
        slot.player
        for slot in team.starters + team.bench
        if slot.player and slot.slot not in ("IR", "TAXI") and player_ppg(slot.player) is not None
    ]
    if not pool or not team.lineup_slots:
        return None
    order = sorted(
        enumerate(team.lineup_slots),
        key=lambda item: (
            0 if item[1] in {"QB", "K", "DEF"} else 1 if item[1] in {"RB", "WR", "TE"} else 2,
            item[0],
        ),
    )
    remaining = list(pool)
    total = 0.0
    filled = 0
    for _index, slot in order:
        eligible = [player for player in remaining if is_eligible(player, slot)]
        if not eligible:
            continue
        best = max(eligible, key=lambda player: player_ppg(player) or 0.0)
        total += player_ppg(best) or 0.0
        remaining.remove(best)
        filled += 1
    if filled == 0:
        return None
    return round(total, 1)


def _tradeable(team: TeamOut) -> list[PlayerOut]:
    players: list[PlayerOut] = []
    for slot in team.starters + team.bench:
        player = slot.player
        if player is None or slot.slot in ("IR", "TAXI"):
            continue
        if player_ppg(player) is None:
            continue
        status = (player.injury_status or "").upper()
        if status in {"IR", "OUT", "SUS", "SUSPENDED"}:
            continue
        players.append(player)
    return players


def _with_exchange(team: TeamOut, send: list[PlayerOut], receive: list[PlayerOut]) -> TeamOut:
    """Return a shallow team view after swapping the listed players."""
    send_ids = {player.id for player in send}
    kept = [
        slot
        for slot in team.starters + team.bench + team.reserve
        if not (slot.player and slot.player.id in send_ids)
    ]
    added = [RosterSlotOut(slot="BN", player=player, is_starter=False) for player in receive]
    starters = [slot for slot in kept if slot.is_starter]
    bench = [slot for slot in kept if not slot.is_starter and slot.slot == "BN"] + added
    reserve = [slot for slot in kept if not slot.is_starter and slot.slot in ("IR", "TAXI")]
    return team.model_copy(update={"starters": starters, "bench": bench, "reserve": reserve})


@dataclass
class MutualTrade:
    give: list[PlayerOut]
    receive: list[PlayerOut]
    opponent_team_id: UUID
    opponent_name: str
    user_ppg_before: float
    user_ppg_after: float
    partner_ppg_before: float
    partner_ppg_after: float
    user_delta: float
    partner_delta: float
    message: str


def _packages(players: list[PlayerOut], *, max_size: int = 2) -> list[list[PlayerOut]]:
    packages: list[list[PlayerOut]] = [[player] for player in players]
    if max_size >= 2 and len(players) >= 2:
        ranked = sorted(players, key=lambda player: player_ppg(player) or 0.0)
        # Prefer packaging lower-PPG depth so stars stay put.
        for left, right in combinations(ranked[: min(6, len(ranked))], 2):
            packages.append([left, right])
    return packages


def _package_value(players: list[PlayerOut]) -> float:
    return sum(player_ppg(player) or 0.0 for player in players)


def find_mutual_ppg_trades(
    user: TeamOut,
    opponents: list[TeamOut],
    *,
    limit: int = 12,
    min_gain: float = 0.3,
) -> list[MutualTrade]:
    """Scan 1-for-1, 2-for-1, and 1-for-2 swaps that raise both teams' starter PPG."""
    user_before = optimal_starter_ppg(user)
    if user_before is None:
        return []
    mine = _tradeable(user)
    my_packages = _packages(mine)
    found: list[MutualTrade] = []
    for partner in opponents:
        if partner.team.id == user.team.id:
            continue
        partner_before = optimal_starter_ppg(partner)
        if partner_before is None:
            continue
        their_packages = _packages(_tradeable(partner))
        for give in my_packages:
            for receive in their_packages:
                if len(give) > 1 and len(receive) > 1:
                    continue
                # Skip obvious rip-offs: package PPG should stay in the same ballpark.
                if abs(_package_value(give) - _package_value(receive)) > 12:
                    continue
                after_user = optimal_starter_ppg(_with_exchange(user, give, receive))
                after_partner = optimal_starter_ppg(_with_exchange(partner, receive, give))
                if after_user is None or after_partner is None:
                    continue
                user_delta = round(after_user - user_before, 1)
                partner_delta = round(after_partner - partner_before, 1)
                if user_delta < min_gain or partner_delta < min_gain:
                    continue
                give_names = ", ".join(player.name for player in give)
                receive_names = ", ".join(player.name for player in receive)
                found.append(
                    MutualTrade(
                        give=give,
                        receive=receive,
                        opponent_team_id=partner.team.id,
                        opponent_name=partner.team.name,
                        user_ppg_before=user_before,
                        user_ppg_after=after_user,
                        partner_ppg_before=partner_before,
                        partner_ppg_after=after_partner,
                        user_delta=user_delta,
                        partner_delta=partner_delta,
                        message=(
                            f"Offer {give_names} to {partner.team.name} for {receive_names}. "
                            f"Your starters rise {user_delta:+g} PPG and theirs rise {partner_delta:+g} PPG."
                        ),
                    )
                )
    found.sort(key=lambda row: (-(row.user_delta + row.partner_delta), -row.user_delta, row.opponent_name))
    seen: set[UUID] = set()
    unique: list[MutualTrade] = []
    for row in found:
        if row.opponent_team_id in seen:
            continue
        seen.add(row.opponent_team_id)
        unique.append(row)
        if len(unique) >= limit:
            break
    return unique
