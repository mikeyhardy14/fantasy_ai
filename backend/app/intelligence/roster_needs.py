"""Positional depth grading. Pure functions."""

from collections import Counter

from app.domain.enums import NON_LINEUP_SLOTS, OFFENSE_POSITIONS, SLOT_ELIGIBILITY
from app.intelligence.lineup import is_healthy, is_unavailable
from app.schemas.league import PositionNeedOut, RosterNeedsOut, RosterSlotOut

GRADE_ORDER = {"Weak": 0, "Needs depth": 1, "Adequate": 2, "Strong": 3}


def required_starters(lineup_slots: list[str]) -> tuple[Counter, int]:
    """Exact-position requirements plus the number of flex slots."""
    exact: Counter = Counter()
    flex = 0
    for slot in lineup_slots:
        if slot in NON_LINEUP_SLOTS:
            continue
        if slot in SLOT_ELIGIBILITY and len(SLOT_ELIGIBILITY[slot]) > 1:
            flex += 1
        else:
            exact[SLOT_ELIGIBILITY.get(slot, (slot,))[0]] += 1
    return exact, flex


def grade_position(position: str, required: int, healthy: int, total: int, flex_slots: int) -> tuple[str, list[str]]:
    notes: list[str] = []
    if required == 0 and position not in ("RB", "WR", "TE"):
        # Position not used by this league.
        return "Adequate", notes
    if healthy < required:
        notes.append(f"Only {healthy} healthy {position} for {required} starting slot(s).")
        return "Weak", notes
    spare = healthy - required
    flex_relevant = position in ("RB", "WR", "TE") and flex_slots > 0
    if position in ("QB", "K", "DEF"):
        if spare == 0:
            return "Adequate", notes
        notes.append(f"{spare} spare {position} on the bench.")
        return "Strong", notes
    if spare == 0:
        notes.append(f"No healthy {position} depth beyond the starters" + (" and flex." if flex_relevant else "."))
        return "Needs depth", notes
    if spare == 1:
        if flex_relevant:
            notes.append(f"Only one spare {position}, who likely fills a flex slot.")
            return "Needs depth" if position != "TE" else "Adequate", notes
        return "Adequate", notes
    return "Strong", notes


def compute_roster_needs(
    lineup_slots: list[str],
    roster: list[RosterSlotOut],
    max_roster_size: int | None,
) -> RosterNeedsOut:
    exact, flex_slots = required_starters(lineup_slots)
    positions: list[PositionNeedOut] = []
    for pos in OFFENSE_POSITIONS:
        players = [s for s in roster if s.player and (s.player.position == pos) and s.slot not in ("IR", "TAXI")]
        total = len(players)
        healthy = len([s for s in players if is_healthy(s)])
        available = len([s for s in players if not is_unavailable(s)])
        required = exact.get(pos, 0)
        starters_healthy = len([s for s in players if s.is_starter and not is_unavailable(s)])
        grade, notes = grade_position(pos, required, available, total, flex_slots)
        if required and starters_healthy < required:
            notes.append(f"{required - starters_healthy} starting {pos} slot(s) currently hold an unavailable player.")
        if healthy < available:
            notes.append(f"{available - healthy} {pos} carrying a questionable/injury designation.")
        positions.append(
            PositionNeedOut(
                position=pos,
                required_starters=required,
                healthy_starters=starters_healthy,
                total_depth=total,
                healthy_depth=healthy,
                grade=grade,
                notes=notes,
            )
        )

    used = [p for p in positions if p.required_starters > 0 or p.total_depth > 0]
    ordered = sorted(used, key=lambda p: (GRADE_ORDER[p.grade], p.healthy_depth - p.required_starters))
    weakest = [p.position for p in ordered if p.grade in ("Weak", "Needs depth")][:3]
    strongest = [p.position for p in reversed(ordered) if p.grade == "Strong"][:3]
    surplus = [
        p.position
        for p in used
        if p.grade == "Strong"
        and (p.healthy_depth - p.required_starters) >= (3 if p.position in ("RB", "WR") else 1)
    ]
    roster_size = len([s for s in roster if s.player and s.slot not in ("IR", "TAXI")])
    open_spots = max(0, (max_roster_size or roster_size) - roster_size) if max_roster_size else 0
    return RosterNeedsOut(
        positions=positions,
        weakest_positions=weakest,
        strongest_positions=strongest,
        surplus_positions=surplus,
        open_roster_spots=open_spots,
        roster_size=roster_size,
        max_roster_size=max_roster_size,
    )
