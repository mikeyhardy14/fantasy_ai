"""Lineup legality, slot eligibility and start/sit swap detection. Pure functions."""

from dataclasses import dataclass

from app.domain.enums import INJURY_SEVERITY, NON_LINEUP_SLOTS, SLOT_ELIGIBILITY
from app.schemas.league import PlayerOut, RosterSlotOut

UNAVAILABLE_FLAGS = {"OUT", "IR", "BYE", "DOUBTFUL", "SUSPENDED", "INACTIVE"}


def eligible_positions_for_slot(slot: str) -> tuple[str, ...]:
    return SLOT_ELIGIBILITY.get(slot, (slot,))


def is_eligible(player: PlayerOut, slot: str) -> bool:
    if slot in NON_LINEUP_SLOTS:
        return True
    positions = set(player.fantasy_positions or ([player.position] if player.position else []))
    return bool(positions & set(eligible_positions_for_slot(slot)))


def injury_severity(player: PlayerOut) -> int:
    if not player.injury_status:
        return 0
    return INJURY_SEVERITY.get(player.injury_status, 2)


def player_flags(player: PlayerOut, week: int) -> list[str]:
    flags: list[str] = []
    if player.on_bye or (player.bye_week is not None and player.bye_week == week):
        flags.append("BYE")
    status = (player.injury_status or "").upper()
    if status in {"IR", "PUP"}:
        flags.append("IR")
    elif status in {"OUT", "O"}:
        flags.append("OUT")
    elif status in {"SUS"}:
        flags.append("SUSPENDED")
    elif status in {"DOUBTFUL", "D"}:
        flags.append("DOUBTFUL")
    elif status in {"QUESTIONABLE", "Q"}:
        flags.append("QUESTIONABLE")
    elif status:
        flags.append("INJURED")
    if (player.status or "").lower() in {"inactive", "injured reserve"} and "IR" not in flags:
        flags.append("INACTIVE")
    if not player.nfl_team:
        flags.append("FREE_AGENT_NFL")
    return flags


def is_unavailable(slot: RosterSlotOut) -> bool:
    return bool(set(slot.flags) & UNAVAILABLE_FLAGS)


def is_healthy(slot: RosterSlotOut) -> bool:
    return not (set(slot.flags) & (UNAVAILABLE_FLAGS | {"QUESTIONABLE", "INJURED"}))


def lineup_issues(starters: list[RosterSlotOut], lineup_slots: list[str]) -> list[str]:
    issues: list[str] = []
    filled = {s.slot_index for s in starters if s.player is not None}
    for idx, slot in enumerate(lineup_slots):
        if idx not in filled:
            issues.append(f"{slot} slot is empty.")
    for s in starters:
        if s.player is None:
            continue
        if not is_eligible(s.player, s.slot):
            issues.append(f"{s.player.name} ({s.player.position}) is not eligible for {s.slot}.")
        if "BYE" in s.flags:
            issues.append(f"{s.player.name} ({s.slot}) is on bye this week.")
        elif "IR" in s.flags or "OUT" in s.flags:
            issues.append(f"{s.player.name} ({s.slot}) is {s.player.injury_status or 'out'}.")
        elif "DOUBTFUL" in s.flags:
            issues.append(f"{s.player.name} ({s.slot}) is doubtful.")
    return issues


@dataclass
class SwapSuggestion:
    slot: str
    starter: RosterSlotOut
    replacement: RosterSlotOut
    reason: str
    projection_delta: float | None
    urgency: str  # HIGH | MEDIUM | LOW


def _proj(slot: RosterSlotOut) -> float | None:
    return slot.player.projected_points if slot.player else None


def suggest_swaps(starters: list[RosterSlotOut], bench: list[RosterSlotOut]) -> list[SwapSuggestion]:
    """Find bench players who should replace unavailable / clearly worse starters.

    Uses projections only when both players have them; otherwise only
    availability (bye/injury) drives the suggestion.
    """
    suggestions: list[SwapSuggestion] = []
    used_bench: set[str] = set()

    def bench_candidates(slot: str) -> list[RosterSlotOut]:
        cands = [
            b
            for b in bench
            if b.player
            and str(b.player.id) not in used_bench
            and is_eligible(b.player, slot)
            and not is_unavailable(b)
        ]
        # Best projection first; unknown projections last but still eligible.
        cands.sort(key=lambda b: (_proj(b) is None, -(_proj(b) or 0.0), injury_severity(b.player)))  # type: ignore[arg-type]
        return cands

    # 1) Unavailable starters first (highest urgency)
    for s in sorted(starters, key=lambda x: not is_unavailable(x)):
        if s.player is None:
            continue
        if is_unavailable(s):
            cands = bench_candidates(s.slot)
            if not cands:
                continue
            repl = cands[0]
            reason_flag = "on bye" if "BYE" in s.flags else (s.player.injury_status or "unavailable")
            delta = None
            if _proj(repl) is not None and _proj(s) is not None:
                delta = round(_proj(repl) - _proj(s), 1)  # type: ignore[operator]
            suggestions.append(
                SwapSuggestion(
                    slot=s.slot,
                    starter=s,
                    replacement=repl,
                    reason=f"{s.player.name} is {reason_flag}; {repl.player.name} is healthy and eligible for {s.slot}.",  # type: ignore[union-attr]
                    projection_delta=delta,
                    urgency="HIGH",
                )
            )
            used_bench.add(str(repl.player.id))  # type: ignore[union-attr]

    # 2) Projection-driven upgrades for healthy starters
    for s in starters:
        if s.player is None or is_unavailable(s) or _proj(s) is None:
            continue
        cands = [b for b in bench_candidates(s.slot) if _proj(b) is not None and is_healthy(b)]
        if not cands:
            continue
        best = cands[0]
        delta = round(_proj(best) - _proj(s), 1)  # type: ignore[operator]
        threshold = 2.0 if "QUESTIONABLE" not in s.flags else 0.5
        if delta >= threshold:
            suggestions.append(
                SwapSuggestion(
                    slot=s.slot,
                    starter=s,
                    replacement=best,
                    reason=(
                        f"{best.player.name} projects {_proj(best):.1f} vs {_proj(s):.1f} for {s.player.name} at {s.slot}"  # type: ignore[union-attr]
                        + (" (who is also questionable)" if "QUESTIONABLE" in s.flags else "")
                        + "."
                    ),
                    projection_delta=delta,
                    urgency="MEDIUM" if delta < 5 else "HIGH",
                )
            )
            used_bench.add(str(best.player.id))  # type: ignore[union-attr]
    return suggestions
