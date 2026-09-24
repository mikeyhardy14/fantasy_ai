"""Rule-based recommendation engine. No LLM involved.

The LLM layer later explains and prioritises these, but every recommendation
here is derivable from stored data alone.
"""

from app.domain.enums import Priority, RecommendationType
from app.domain.recommendation import Recommendation
from app.intelligence.context import TeamContext
from app.intelligence.lineup import is_unavailable, suggest_swaps
from app.schemas.league import PlayerOut, RosterSlotOut


def _pid(slot: RosterSlotOut) -> str:
    return str(slot.player.id) if slot.player else ""


def _pname(slot: RosterSlotOut) -> str:
    return slot.player.name if slot.player else "Empty"


def _proj_text(player: PlayerOut) -> str:
    if player.projected_points is None:
        return "projection unavailable"
    return f"projected {player.projected_points:.1f}"


def injury_recommendations(ctx: TeamContext) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for s in ctx.team.starters:
        if not s.player or not s.player.injury_status:
            continue
        flags = set(s.flags)
        if flags & {"OUT", "IR", "DOUBTFUL", "SUSPENDED"}:
            priority = Priority.HIGH
            verb = "is"
        elif "QUESTIONABLE" in flags:
            priority = Priority.MEDIUM
            verb = "is"
        else:
            priority = Priority.LOW
            verb = "is listed as"
        body = f" ({s.player.injury_body_part})" if s.player.injury_body_part else ""
        recs.append(
            Recommendation(
                type=RecommendationType.INJURY_ALERT,
                priority=priority,
                title=f"{s.player.name} ({s.slot}) {verb} {s.player.injury_status}",
                reason=f"Your starting {s.slot} {s.player.name} {verb} {s.player.injury_status}{body}. "
                + ("Replace before kickoff." if priority == Priority.HIGH else "Monitor practice reports and have a backup ready."),
                players=[_pid(s)],
                player_names=[s.player.name],
                position=s.player.position,
                data={"slot": s.slot, "injury_status": s.player.injury_status},
            )
        )
    return recs


def bye_recommendations(ctx: TeamContext) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for s in ctx.team.starters:
        if s.player and "BYE" in s.flags:
            recs.append(
                Recommendation(
                    type=RecommendationType.BYE_WEEK,
                    priority=Priority.HIGH,
                    title=f"{s.player.name} ({s.slot}) is on bye in Week {ctx.week}",
                    reason=f"{s.player.name}'s team ({s.player.nfl_team}) does not play in Week {ctx.week}. A starter on bye scores zero.",
                    players=[_pid(s)],
                    player_names=[s.player.name],
                    position=s.player.position,
                    data={"slot": s.slot},
                )
            )
    if ctx.bye_weeks_available:
        upcoming = [
            s
            for s in ctx.team.starters
            if s.player and s.player.bye_week == ctx.week + 1
        ]
        if len(upcoming) >= 2:
            names = [s.player.name for s in upcoming if s.player]
            recs.append(
                Recommendation(
                    type=RecommendationType.BYE_WEEK,
                    priority=Priority.LOW,
                    title=f"{len(upcoming)} starters on bye next week",
                    reason=f"Week {ctx.week + 1}: {', '.join(names)} are all on bye. Plan replacements now.",
                    players=[_pid(s) for s in upcoming],
                    player_names=names,
                )
            )
    return recs


def start_sit_recommendations(ctx: TeamContext) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for swap in suggest_swaps(ctx.team.starters, ctx.team.bench):
        delta = swap.projection_delta
        data = {"slot": swap.slot, "projection_delta": delta}
        recs.append(
            Recommendation(
                type=RecommendationType.START_SIT,
                priority=Priority(swap.urgency),
                title=f"Start {_pname(swap.replacement)} over {_pname(swap.starter)} at {swap.slot}",
                reason=swap.reason
                + (f" Projected gain: +{delta:.1f}." if delta is not None and delta > 0 else ""),
                players=[_pid(swap.replacement), _pid(swap.starter)],
                player_names=[_pname(swap.replacement), _pname(swap.starter)],
                position=swap.replacement.player.position if swap.replacement.player else None,
                data=data,
            )
        )
    return recs


def weakness_and_waiver_recommendations(ctx: TeamContext) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for need in ctx.needs.positions:
        if need.grade not in ("Weak", "Needs depth"):
            continue
        priority = Priority.HIGH if need.grade == "Weak" else Priority.MEDIUM
        recs.append(
            Recommendation(
                type=RecommendationType.ROSTER_WEAKNESS,
                priority=priority,
                title=f"{need.position} depth is {need.grade.lower()}",
                reason=" ".join(need.notes)
                or f"You have {need.healthy_depth} healthy {need.position} for {need.required_starters} starting slot(s).",
                position=need.position,
                data={"grade": need.grade, "healthy_depth": need.healthy_depth, "required": need.required_starters},
            )
        )
        candidates = ctx.available_at(need.position, limit=3)
        if candidates:
            top = candidates[0]
            recs.append(
                Recommendation(
                    type=RecommendationType.WAIVER_TARGET,
                    priority=priority,
                    title=f"Waiver target: {top.name} ({need.position}, {top.nfl_team or 'FA'})",
                    reason=f"{need.position} is your {need.grade.lower()} position. {top.name} is available ({_proj_text(top)}). "
                    f"Other options: {', '.join(p.name for p in candidates[1:]) or 'none'}.",
                    players=[str(p.id) for p in candidates],
                    player_names=[p.name for p in candidates],
                    position=need.position,
                    data={"projections_available": ctx.projections_available},
                )
            )
        else:
            recs.append(
                Recommendation(
                    type=RecommendationType.WAIVER_TARGET,
                    priority=Priority.LOW,
                    title=f"Look for {need.position} help on waivers",
                    reason=f"No healthy {need.position} are available in the player pool right now; keep checking after waivers clear.",
                    position=need.position,
                )
            )
    return recs


def drop_candidate_recommendations(ctx: TeamContext) -> list[Recommendation]:
    recs: list[Recommendation] = []
    if ctx.needs.open_roster_spots > 0:
        return recs
    for s in ctx.team.bench:
        if not s.player:
            continue
        if set(s.flags) & {"IR", "OUT", "INACTIVE", "FREE_AGENT_NFL"} and s.slot != "IR":
            recs.append(
                Recommendation(
                    type=RecommendationType.DROP_PLAYER,
                    priority=Priority.LOW,
                    title=f"Drop candidate: {s.player.name}",
                    reason=f"{s.player.name} is {s.player.injury_status or s.player.status or 'unavailable'} and occupying a bench spot on a full roster. "
                    "Consider moving him to IR (if eligible) or dropping for a waiver add.",
                    players=[_pid(s)],
                    player_names=[s.player.name],
                    position=s.player.position,
                )
            )
    return recs


def trade_recommendations(ctx: TeamContext) -> list[Recommendation]:
    recs: list[Recommendation] = []
    if ctx.needs.surplus_positions and ctx.needs.weakest_positions:
        give = ", ".join(ctx.needs.surplus_positions)
        target = ", ".join(ctx.needs.weakest_positions)
        recs.append(
            Recommendation(
                type=RecommendationType.TRADE_TARGET,
                priority=Priority.MEDIUM,
                title=f"Trade from {give} depth to acquire {target}",
                reason=f"Your roster has surplus at {give} and is thin at {target}. Packaging depth for a starter at a weak position raises your weekly floor.",
                data={"give_positions": ctx.needs.surplus_positions, "target_positions": ctx.needs.weakest_positions},
            )
        )
    return recs


def generate_recommendations(ctx: TeamContext) -> list[Recommendation]:
    recs: list[Recommendation] = []
    recs += injury_recommendations(ctx)
    recs += bye_recommendations(ctx)
    recs += start_sit_recommendations(ctx)
    recs += weakness_and_waiver_recommendations(ctx)
    recs += drop_candidate_recommendations(ctx)
    recs += trade_recommendations(ctx)
    # De-duplicate identical titles, keep highest priority first.
    seen: set[str] = set()
    unique: list[Recommendation] = []
    for rec in sorted(recs, key=lambda r: r.priority_rank):
        if rec.title in seen:
            continue
        seen.add(rec.title)
        unique.append(rec)
    return unique


def unavailable_starters(ctx: TeamContext) -> list[RosterSlotOut]:
    return [s for s in ctx.team.starters if s.player and is_unavailable(s)]
