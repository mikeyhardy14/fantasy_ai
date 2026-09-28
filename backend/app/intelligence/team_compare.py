"""Side-by-side team numbers. The write-up quotes these figures and does not add any."""

from app.nfl_data.vegas import normalize_position
from app.schemas.ai import ComparePosition, CompareSide, CompareStarter
from app.schemas.league import RosterNeedsOut, TeamOut

_OUT = {"OUT", "IR", "DOUBTFUL", "SUSPENDED", "INACTIVE"}


def comparison_side(team: TeamOut, needs: RosterNeedsOut) -> CompareSide:
    by_position: dict[str, float] = {}
    known: dict[str, bool] = {}
    starters: list[CompareStarter] = []
    out = 0
    bye = 0
    for slot in team.starters:
        player = slot.player
        if player is None:
            continue
        flags = set(slot.flags)
        on_bye = "BYE" in flags or player.on_bye
        if on_bye:
            bye += 1
        if flags & _OUT:
            out += 1
        position = normalize_position(player.position)
        if position and player.projected_points is not None:
            by_position[position] = by_position.get(position, 0.0) + player.projected_points
            known[position] = True
        starters.append(
            CompareStarter(
                name=player.name,
                slot=slot.slot,
                position=position or player.position,
                projected_points=player.projected_points,
                points=slot.points,
                injury_status=player.injury_status,
                on_bye=on_bye,
            )
        )
    positions = [
        ComparePosition(
            position=row.position,
            grade=row.grade,
            healthy_depth=row.healthy_depth,
            total_depth=row.total_depth,
            starter_projection=round(by_position[row.position], 1) if known.get(row.position) else None,
        )
        for row in needs.positions
        if row.required_starters or row.total_depth
    ]
    summary = team.team
    return CompareSide(
        team_id=summary.id,
        name=summary.name,
        owner_name=summary.owner_name,
        is_user_team=summary.is_user_team,
        record=summary.record,
        points_for=summary.points_for,
        points_against=summary.points_against,
        projected_points=team.projected_points,
        faab_remaining=summary.faab_remaining,
        waiver_position=summary.waiver_position,
        starters_out=out,
        starters_on_bye=bye,
        positions=positions,
        starters=starters,
    )


def comparison_summary(sides: list[CompareSide]) -> str:
    left, right = sides
    sentences = [
        (
            f"{left.name} is {left.record} with {_num(left.points_for)} points for and {_num(left.points_against)} against. "
            f"{right.name} is {right.record} with {_num(right.points_for)} points for and {_num(right.points_against)} against."
        )
    ]
    if left.projected_points is not None and right.projected_points is not None:
        leader, other = (left, right) if left.projected_points >= right.projected_points else (right, left)
        sentences.append(
            f"This week {leader.name} projects {_num(leader.projected_points)} to {other.name}'s {_num(other.projected_points)}."
        )
    edges: list[str] = []
    other_positions = {row.position: row for row in right.positions}
    for row in left.positions:
        other = other_positions.get(row.position)
        if other is None or row.starter_projection is None or other.starter_projection is None:
            continue
        if abs(row.starter_projection - other.starter_projection) < 0.5 and row.grade == other.grade:
            continue
        if row.starter_projection >= other.starter_projection:
            lead, lead_row, trail = left, row, other
        else:
            lead, lead_row, trail = right, other, row
        edges.append(
            f"{lead.name} is ahead at {row.position} ({_num(lead_row.starter_projection)} from starters, {lead_row.grade}, "
            f"{lead_row.healthy_depth}/{lead_row.total_depth} healthy) against {_num(trail.starter_projection)} and {trail.grade}."
        )
    if edges:
        sentences.append(" ".join(edges))
    health = [
        f"{side.name} has {side.starters_out} starter{'s' if side.starters_out != 1 else ''} who cannot play and {side.starters_on_bye} on bye."
        for side in sides
        if side.starters_out or side.starters_on_bye
    ]
    if health:
        sentences.append(" ".join(health))
    return " ".join(sentences)


def _num(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}"
