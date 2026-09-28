"""Pick who to offer for one rostered player. The model may rewrite the choice."""

from app.schemas.league import PlayerOut, RosterNeedsOut, RosterSlotOut


def pick_give(slots: list[RosterSlotOut], target: PlayerOut, needs: RosterNeedsOut) -> list[RosterSlotOut]:
    """One player from the user's roster, preferring surplus bench depth near the target's value."""
    pool = [slot for slot in slots if slot.player and slot.slot not in ("IR", "TAXI")]
    if not pool:
        pool = [slot for slot in slots if slot.player]
    if not pool:
        return []
    grades = {row.position: row.grade for row in needs.positions}
    target_points = target.projected_points

    def key(slot: RosterSlotOut) -> tuple:
        player = slot.player
        assert player is not None
        grade = grades.get(player.position or "")
        thin = 0 if grade == "Strong" else 1 if grade not in ("Weak", "Needs depth") else 2
        starter = 1 if slot.is_starter else 0
        points = player.projected_points
        if target_points is None or points is None:
            gap = 0.0
        else:
            gap = abs(points - target_points)
            if points > target_points + 3:
                gap += 10
        return (thin, starter, gap, player.name)

    return [min(pool, key=key)]


def offer_message(give: list[PlayerOut], receive: PlayerOut, opponent_name: str) -> str:
    names = ", ".join(player.name for player in give)
    return f"Offer {names} to {opponent_name} for {receive.name}."
