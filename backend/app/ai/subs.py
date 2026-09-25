"""Turn "sub Lamar Jackson" into lineup buttons. The click performs the move."""

import re

from app.ai.approvals import lineup_action
from app.ai.tools.league_tools import find_roster_player
from app.intelligence.lineup import is_eligible
from app.schemas.ai import LineupAction
from app.schemas.league import RosterSlotOut, TeamOut

_LEAD = re.compile(
    r"^\s*(?:please\s+)?(?:can you\s+|could you\s+|i want to\s+|i'd like to\s+|lets\s+|let's\s+)?"
    r"(?:sub|substitute|swap)\b(?:\s+(?:out|in))?\s+(.+?)\s*$",
    re.IGNORECASE,
)
_PAIR = re.compile(r"\s+(?:for|with|and)\s+", re.IGNORECASE)
_TRAILING = re.compile(r"\s+(?:out|please|this week|right now|for me)$", re.IGNORECASE)
_LEADING = re.compile(r"^(?:out|in)\s+", re.IGNORECASE)
_BLOCKED = {"BYE", "OUT", "SUSPENDED", "IR"}
_LIMIT = 8


def sub_proposal(team: TeamOut, week: int, question: str) -> tuple[str, list[LineupAction]] | None:
    """Options for a sub request. None when the message is not asking to sub."""
    names = _names(question)
    if names is None:
        return None
    roster = team.starters + team.bench + team.reserve
    if len(names) == 2:
        return _pair(team, week, roster, names[0], names[1])
    return _one(team, week, roster, names[0])


def _names(question: str) -> list[str] | None:
    match = _LEAD.match(question.strip())
    if not match:
        return None
    text = match.group(1).strip().strip("?.!")
    text = _TRAILING.sub("", text).strip()
    text = _LEADING.sub("", text).strip()
    if not text or text.lower() in {"my lineup", "the lineup", "lineup", "this week's lineup"}:
        return None
    parts = [part.strip() for part in _PAIR.split(text, maxsplit=1) if part.strip()]
    return parts[:2]


def _one(team: TeamOut, week: int, roster: list[RosterSlotOut], name: str) -> tuple[str, list[LineupAction]]:
    row, error = find_roster_player(roster, name)
    if error or row is None or row.player is None:
        return error or "Name a player on the roster.", []
    if row.is_starter and row.slot_index is not None:
        return _replacements(team, week, row)
    return _destinations(team, week, row)


def _pair(
    team: TeamOut, week: int, roster: list[RosterSlotOut], first: str, second: str
) -> tuple[str, list[LineupAction]]:
    left, left_error = find_roster_player(roster, first)
    right, right_error = find_roster_player(roster, second)
    if left_error or left is None or left.player is None:
        return left_error or "Name a player on the roster.", []
    if right_error or right is None or right.player is None:
        return right_error or "Name a player on the roster.", []
    # "sub A for B" brings A in for B when B is the starter.
    if right.is_starter and right.slot_index is not None and not left.is_starter:
        return _direct(team, week, incoming=left, outgoing=right)
    if left.is_starter and left.slot_index is not None and not right.is_starter:
        return _direct(team, week, incoming=right, outgoing=left)
    if left.is_starter and right.is_starter:
        return f"{left.player.name} and {right.player.name} are both already starting.", []
    return f"Neither {left.player.name} nor {right.player.name} is starting. Name the starter to replace.", []


def _direct(team: TeamOut, week: int, incoming: RosterSlotOut, outgoing: RosterSlotOut) -> tuple[str, list[LineupAction]]:
    assert incoming.player is not None and outgoing.player is not None and outgoing.slot_index is not None
    slot = team.lineup_slots[outgoing.slot_index]
    if not is_eligible(incoming.player, slot):
        return f"{incoming.player.name} is not eligible for {outgoing.player.name}'s {slot} spot.", []
    if set(incoming.flags) & _BLOCKED:
        return f"{incoming.player.name} cannot play this week.", []
    action = _action(
        week,
        incoming,
        slot_index=outgoing.slot_index,
        slot=slot,
        replaces=outgoing.player.name,
        replaces_points=outgoing.player.projected_points,
        incoming=True,
    )
    return (
        f"Sub {incoming.player.name} in for {outgoing.player.name} at {slot}.",
        [action],
    )


def _replacements(team: TeamOut, week: int, starter: RosterSlotOut) -> tuple[str, list[LineupAction]]:
    assert starter.player is not None and starter.slot_index is not None
    slot = team.lineup_slots[starter.slot_index]
    candidates = [
        row
        for row in _available(team)
        if row.player is not None and row.player.id != starter.player.id and is_eligible(row.player, slot)
    ]
    candidates.sort(key=_rank)
    shown = candidates[:_LIMIT]
    actions = [
        _action(
            week,
            row,
            slot_index=starter.slot_index,
            slot=slot,
            replaces=starter.player.name,
            replaces_points=starter.player.projected_points,
            incoming=True,
        )
        for row in shown
    ]
    status = _status(starter)
    extra = ""
    if len(candidates) > _LIMIT:
        extra = f" Showing the {_LIMIT} highest projections."
    if not actions:
        return f"**{starter.player.name}** is starting at {slot}.{status} Nobody on the bench or IR can take that spot.", []
    return (
        f"**{starter.player.name}** is starting at {slot}.{status} Choose who takes that spot.{extra}",
        actions,
    )


def _destinations(team: TeamOut, week: int, bench: RosterSlotOut) -> tuple[str, list[LineupAction]]:
    assert bench.player is not None
    if set(bench.flags) & _BLOCKED:
        return f"{bench.player.name} cannot play this week.", []
    actions: list[LineupAction] = []
    for index, slot in enumerate(team.lineup_slots):
        if not is_eligible(bench.player, slot):
            continue
        occupant = next((row for row in team.starters if row.slot_index == index and row.player), None)
        actions.append(
            _action(
                week,
                bench,
                slot_index=index,
                slot=slot,
                replaces=occupant.player.name if occupant and occupant.player else None,
                replaces_points=occupant.player.projected_points if occupant and occupant.player else None,
                incoming=False,
            )
        )
    if not actions:
        return f"{bench.player.name} is not eligible for any starting slot.", []
    where = "on IR" if bench.slot == "IR" else "on the bench"
    return f"**{bench.player.name}** is {where}. Choose the starter to replace.", actions


def _available(team: TeamOut) -> list[RosterSlotOut]:
    rows = list(team.bench)
    rows.extend(row for row in team.reserve if row.slot == "IR")
    return [row for row in rows if row.player is not None and not (set(row.flags) & _BLOCKED)]


def _rank(row: RosterSlotOut) -> tuple:
    points = row.player.projected_points if row.player else None
    name = row.player.name if row.player else ""
    return (points is None, -(points or 0), name)


def _status(row: RosterSlotOut) -> str:
    if "BYE" in row.flags:
        return " He is on bye."
    if "OUT" in row.flags or "IR" in row.flags:
        return " He is out."
    if "DOUBTFUL" in row.flags:
        return " He is doubtful."
    return ""


def _action(
    week: int,
    row: RosterSlotOut,
    *,
    slot_index: int,
    slot: str,
    replaces: str | None,
    replaces_points: float | None,
    incoming: bool,
) -> LineupAction:
    return lineup_action(
        week,
        row,
        slot_index=slot_index,
        slot=slot,
        replaces=replaces,
        replaces_points=replaces_points,
        incoming=incoming,
    )
