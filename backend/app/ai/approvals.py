"""A start-over stays a proposal until the manager approves it."""

from __future__ import annotations

from uuid import UUID

from app.intelligence.lineup import is_eligible
from app.schemas.ai import LineupAction
from app.schemas.league import RosterSlotOut, TeamOut

_DECLINE = ("not ", "don't ", "dont ", "do not ", "avoid ", "rather than ")


def start_over_summary(
    incoming: str,
    outgoing: str | None,
    slot: str,
    incoming_points: float | None,
    outgoing_points: float | None,
) -> str:
    text = f"Start {incoming} over {outgoing} at {slot}." if outgoing else f"Start {incoming} at {slot}."
    bits: list[str] = []
    if incoming_points is not None:
        bits.append(f"{incoming} {incoming_points:g} projected")
    if outgoing and outgoing_points is not None:
        bits.append(f"{outgoing} {outgoing_points:g} projected")
    if bits:
        text += " " + ", ".join(bits) + "."
    return text


def lineup_action(
    week: int,
    row: RosterSlotOut,
    *,
    slot_index: int,
    slot: str,
    replaces: str | None,
    replaces_points: float | None,
    incoming: bool,
) -> LineupAction:
    assert row.player is not None
    player = row.player
    if incoming:
        label = f"Sub in {player.name}"
    elif replaces:
        label = f"Start over {replaces}"
    else:
        label = f"Start at {slot}"
    bits = [player.position or slot]
    if player.projected_points is not None:
        bits.append(f"{player.projected_points:g} proj")
    if player.injury_status:
        bits.append(player.injury_status)
    return LineupAction(
        label=label,
        summary=start_over_summary(player.name, replaces, slot, player.projected_points, replaces_points),
        player_id=player.id,
        player_name=player.name,
        position=player.position,
        headshot_url=player.headshot_url,
        destination="starter",
        slot_index=slot_index,
        slot=slot,
        week=week,
        replaces=replaces,
        detail=" · ".join(bits),
    )


def start_over_action(team: TeamOut, week: int, incoming: RosterSlotOut, slot_index: int) -> LineupAction | None:
    """The move that puts this player in an occupied slot. None when nobody is sitting there."""
    if incoming.player is None or slot_index < 0 or slot_index >= len(team.lineup_slots):
        return None
    slot = team.lineup_slots[slot_index]
    if not is_eligible(incoming.player, slot):
        return None
    occupant = next((row for row in team.starters if row.slot_index == slot_index and row.player), None)
    if occupant is None or occupant.player is None or occupant.player.id == incoming.player.id:
        return None
    return lineup_action(
        week,
        incoming,
        slot_index=slot_index,
        slot=slot,
        replaces=occupant.player.name,
        replaces_points=occupant.player.projected_points,
        incoming=True,
    )


def swaps_mentioned(team: TeamOut, week: int, message: str) -> list[LineupAction]:
    """Pull 'start A over B' out of an assistant reply and turn each one into a proposal."""
    text = message.lower()
    actions: list[LineupAction] = []
    seen: set[tuple[UUID, int]] = set()
    incoming_rows = [row for row in [*team.bench, *team.reserve] if row.player is not None]
    outgoing_rows = [row for row in team.starters if row.player is not None and row.slot_index is not None]
    for incoming in incoming_rows:
        for outgoing in outgoing_rows:
            assert incoming.player is not None and outgoing.player is not None and outgoing.slot_index is not None
            needle = f"{incoming.player.name.lower()} over {outgoing.player.name.lower()}"
            at = text.find(needle)
            if at < 0 or _declined(text, at):
                continue
            slot = team.lineup_slots[outgoing.slot_index]
            if not is_eligible(incoming.player, slot):
                continue
            key = (incoming.player.id, outgoing.slot_index)
            if key in seen:
                continue
            seen.add(key)
            actions.append(
                lineup_action(
                    week,
                    incoming,
                    slot_index=outgoing.slot_index,
                    slot=slot,
                    replaces=outgoing.player.name,
                    replaces_points=outgoing.player.projected_points,
                    incoming=True,
                )
            )
    return actions


def _declined(text: str, at: int) -> bool:
    window = text[max(0, at - 24) : at]
    return any(phrase in window for phrase in _DECLINE)
