"""Deterministic weekly briefing composed from recommendations and context."""

from app.domain.enums import Priority, RecommendationType
from app.domain.recommendation import Recommendation
from app.intelligence.context import TeamContext
from app.schemas.ai import BriefingItem, PositionAssessment, WeeklyBriefing


def build_briefing(ctx: TeamContext, recs: list[Recommendation]) -> WeeklyBriefing:
    attention = [
        BriefingItem(title=r.title, detail=r.reason, priority=r.priority, type=r.type)
        for r in recs
        if r.type in (RecommendationType.INJURY_ALERT, RecommendationType.BYE_WEEK, RecommendationType.ROSTER_WEAKNESS)
        and r.priority != Priority.LOW
    ][:6]

    actions: list[str] = []
    for r in recs:
        if r.type == RecommendationType.START_SIT:
            actions.append(f"Consider {r.player_names[0]} at {r.data.get('slot', 'the open slot')}")
        elif r.type == RecommendationType.INJURY_ALERT and r.priority == Priority.MEDIUM:
            actions.append(f"Monitor {r.player_names[0]}'s injury status")
        elif r.type == RecommendationType.WAIVER_TARGET and r.position:
            actions.append(f"Look for a {r.position} on waivers")
        elif r.type == RecommendationType.TRADE_TARGET:
            actions.append(r.title)
    # Preserve order, remove duplicates
    seen: set[str] = set()
    actions = [a for a in actions if not (a in seen or seen.add(a))][:6]

    waiver_targets: list[str] = []
    for r in recs:
        if r.type == RecommendationType.WAIVER_TARGET:
            for name in r.player_names:
                if name not in waiver_targets:
                    waiver_targets.append(name)
    waiver_targets = waiver_targets[:5]

    assessment = [
        PositionAssessment(position=p.position, grade=p.grade)
        for p in ctx.needs.positions
        if p.required_starters > 0 or p.total_depth > 0
    ]

    opp = ctx.matchup.opponent.team.name if ctx.matchup and ctx.matchup.opponent else None
    return WeeklyBriefing(
        week=ctx.week,
        team_name=ctx.team.team.name,
        record=ctx.team.team.record,
        opponent_name=opp,
        projected_user=ctx.team.projected_points,
        projected_opponent=ctx.matchup.opponent.projected_points if ctx.matchup and ctx.matchup.opponent else None,
        attention_items=attention,
        recommended_actions=actions,
        waiver_targets=waiver_targets,
        roster_assessment=assessment,
        narrative=None,
        generated_by="deterministic",
    )
