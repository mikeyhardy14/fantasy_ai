"""Deterministic stand-ins used when no OpenAI key is configured (and in tests).

They produce the same schemas as the LLM path from the rule engine's output so
the product stays fully usable offline. Wording is templated, never invented.
"""

from app.domain.enums import RecommendationType
from app.domain.recommendation import Recommendation
from app.intelligence.context import TeamContext
from app.schemas.ai import (
    ChatResponse,
    LineupChange,
    TeamAnalysis,
    TradeAnalysis,
    TradeSideSummary,
    TradeStrategy,
    WaiverPriority,
)
from app.schemas.league import PlayerOut


def _data_gaps(ctx: TeamContext) -> list[str]:
    gaps = []
    if not ctx.projections_available:
        gaps.append("No weekly projections are configured, so lineup and waiver advice is based on availability, depth and roles only.")
    if not ctx.bye_weeks_available:
        gaps.append("Bye-week data is unavailable for this league's players.")
    return gaps


def deterministic_analysis(ctx: TeamContext, recs: list[Recommendation]) -> TeamAnalysis:
    needs = ctx.needs
    team = ctx.team.team
    opp = ctx.matchup.opponent.team.name if ctx.matchup and ctx.matchup.opponent else None

    strengths = []
    for p in needs.positions:
        if p.grade == "Strong":
            strengths.append(f"{p.position}: {p.healthy_depth} healthy players for {p.required_starters} starting slot(s).")
    if not strengths:
        strengths.append("No position currently grades as Strong; depth is spread evenly.")

    weaknesses = []
    for p in needs.positions:
        if p.grade in ("Weak", "Needs depth"):
            weaknesses.append(f"{p.position} is {p.grade.lower()}: " + (" ".join(p.notes) or f"{p.healthy_depth} healthy for {p.required_starters} slot(s)."))
    for r in recs:
        if r.type in (RecommendationType.INJURY_ALERT, RecommendationType.BYE_WEEK) and r.priority != "LOW":
            weaknesses.append(r.title + ".")
    if not weaknesses:
        weaknesses.append("No structural weaknesses detected from roster depth, injuries or byes.")

    lineup_changes = [
        LineupChange(slot=r.data.get("slot", "?"), start_player=r.player_names[0], sit_player=r.player_names[1] if len(r.player_names) > 1 else None, reason=r.reason)
        for r in recs
        if r.type == RecommendationType.START_SIT
    ]

    waiver = []
    for r in recs:
        if r.type == RecommendationType.WAIVER_TARGET and r.position:
            waiver.append(
                WaiverPriority(
                    position=r.position,
                    player_name=r.player_names[0] if r.player_names else None,
                    priority=r.priority.value,
                    reason=r.reason,
                )
            )

    trade = TradeStrategy(
        can_trade_away=needs.surplus_positions,
        should_target=needs.weakest_positions,
        reasoning=(
            f"Surplus at {', '.join(needs.surplus_positions)} can be packaged for help at {', '.join(needs.weakest_positions)}."
            if needs.surplus_positions and needs.weakest_positions
            else "No clear surplus to trade from; focus on waivers for depth."
        ),
    )

    this_week = []
    for r in recs[:6]:
        if r.type == RecommendationType.START_SIT:
            this_week.append(f"Move {r.player_names[0]} into {r.data.get('slot', 'the lineup')} for {r.player_names[1]}.")
        elif r.type == RecommendationType.INJURY_ALERT:
            this_week.append(f"Check {r.player_names[0]}'s status ({r.data.get('injury_status')}) before kickoff.")
        elif r.type == RecommendationType.BYE_WEEK:
            this_week.append(f"Replace {r.player_names[0]} (bye) in your lineup.")
        elif r.type == RecommendationType.WAIVER_TARGET and r.player_names:
            this_week.append(f"Submit a waiver claim for {r.player_names[0]} ({r.position}).")
    if not this_week:
        this_week.append("Your lineup has no flagged issues; confirm it after final injury reports.")

    summary = (
        f"{team.name} is {team.record}"
        + (f" and faces {opp} in Week {ctx.week}." if opp else f" heading into Week {ctx.week}.")
        + f" Strongest: {', '.join(needs.strongest_positions) or 'none'}. Weakest: {', '.join(needs.weakest_positions) or 'none'}."
        + f" {len([r for r in recs if r.priority == 'HIGH'])} high-priority item(s) need attention."
    )
    gaps = _data_gaps(ctx)
    return TeamAnalysis(
        team_summary=summary,
        strengths=strengths,
        weaknesses=weaknesses,
        lineup_changes=lineup_changes,
        waiver_priorities=waiver[:5],
        trade_strategy=trade,
        this_week=this_week[:6],
        data_gaps=gaps,
        confidence="LOW" if len(gaps) >= 2 else "MEDIUM",
    )


def _asked_to_change_lineup(question: str) -> bool:
    q = question.lower()
    if any(k in q for k in ("set my", "set the lineup", "set this week", "change my lineup", "change the lineup")):
        return True
    if "?" in q:
        return False
    return any(k in q for k in ("bench ", "sit ", "move ", "put ", "to ir", "on ir"))


def deterministic_chat(ctx: TeamContext, recs: list[Recommendation], question: str) -> ChatResponse:
    q = question.lower()
    lines: list[str] = []
    if _asked_to_change_lineup(q):
        lines.append("The lineup was not changed.")
        lines.append(
            "Set GEMINI_API_KEY on the server (a free key from Google AI Studio) so the assistant can write this week's Sleeper lineup."
        )
    elif any(k in q for k in ("flex", "start", "sit", "lineup")):
        swaps = [r for r in recs if r.type == RecommendationType.START_SIT]
        lines.append("**Lineup check (rule-based, no AI key configured):**")
        lines += [f"- {r.title}: {r.reason}" for r in swaps] or ["- No lineup changes are indicated by availability or projection data."]
        if ctx.team.lineup_issues:
            lines.append("Issues: " + "; ".join(ctx.team.lineup_issues))
    elif any(k in q for k in ("waiver", "pick up", "add", "drop", "free agent")):
        lines.append("**Waiver outlook:**")
        lines.append(f"Weakest positions: {', '.join(ctx.needs.weakest_positions) or 'none'}.")
        for r in recs:
            if r.type == RecommendationType.WAIVER_TARGET:
                lines.append(f"- {r.title}: {r.reason}")
    elif "trade" in q:
        lines.append("**Trade strategy:**")
        lines.append(f"Surplus: {', '.join(ctx.needs.surplus_positions) or 'none'}. Needs: {', '.join(ctx.needs.weakest_positions) or 'none'}.")
    elif any(k in q for k in ("weak", "strength", "roster", "team")):
        lines.append("**Roster assessment:**")
        lines += [f"- {p.position}: {p.grade}" for p in ctx.needs.positions if p.required_starters or p.total_depth]
    else:
        lines.append("**This week's priorities:**")
        lines += [f"- [{r.priority}] {r.title}: {r.reason}" for r in recs[:6]] or ["- Nothing flagged."]
    lines.append("")
    lines.append(
        "_Set GEMINI_API_KEY on the server for a free assistant that can change this week's lineup. "
        "The items above are computed directly from your league data._"
    )
    return ChatResponse(
        message="\n".join(lines),
        tools_used=["get_roster", "get_roster_needs", "get_recommendations"],
        generated_by="deterministic",
        suggested_questions=["Who should I start at FLEX?", "What position should I target on waivers?", "What are my roster's weaknesses?"],
    )


def deterministic_trade(ctx: TeamContext, give: list[PlayerOut], receive: list[PlayerOut]) -> TradeAnalysis:
    def side(players: list[PlayerOut]) -> TradeSideSummary:
        proj = [p.projected_points for p in players]
        return TradeSideSummary(
            players=[p.name for p in players],
            positions=[p.position or "?" for p in players],
            projected_points=round(sum(x for x in proj if x is not None), 1) if all(x is not None for x in proj) else None,
            injured=[p.name for p in players if p.injury_status],
        )

    g, r = side(give), side(receive)
    needs_by_pos = {p.position: p for p in ctx.needs.positions}
    impact, lineup_impact, risks = [], [], []
    for p in give:
        n = needs_by_pos.get(p.position or "")
        if n and n.grade in ("Weak", "Needs depth"):
            risks.append(f"Trading {p.name} thins an already {n.grade.lower()} {p.position} group.")
        elif n and n.grade == "Strong":
            impact.append(f"{p.position} depth is Strong, so losing {p.name} is affordable.")
    for p in receive:
        n = needs_by_pos.get(p.position or "")
        if n and n.grade in ("Weak", "Needs depth"):
            impact.append(f"{p.name} addresses your {n.grade.lower()} {p.position} position.")
        if p.injury_status:
            risks.append(f"{p.name} is listed {p.injury_status}.")
        if p.bye_week == ctx.week:
            risks.append(f"{p.name} is on bye this week.")
    starters = {s.player.id for s in ctx.team.starters if s.player}
    for p in give:
        if p.id in starters:
            lineup_impact.append(f"{p.name} is a current starter; you will need a replacement at his slot.")
    gaps = []
    if g.projected_points is None or r.projected_points is None:
        gaps.append("Projections unavailable for one or more players; value comparison is positional only.")
    score = 0
    score += len([i for i in impact if "addresses" in i]) - len([x for x in risks if "thins" in x])
    if g.projected_points is not None and r.projected_points is not None:
        score += 1 if r.projected_points > g.projected_points + 2 else (-1 if g.projected_points > r.projected_points + 2 else 0)
    verdict = "UNCLEAR" if gaps and score == 0 else "ACCEPT" if score > 0 else "REJECT" if score < 0 else "NEGOTIATE"
    return TradeAnalysis(
        verdict=verdict,
        summary=f"You give {', '.join(g.players)} for {', '.join(r.players)}. Net positional effect: {'favourable' if score > 0 else 'unfavourable' if score < 0 else 'neutral'} based on roster needs.",
        you_give=g,
        you_receive=r,
        roster_impact=impact or ["No change to graded positional strength."],
        lineup_impact=lineup_impact or ["No current starters are involved."],
        risks=risks or ["No injury or bye risks detected."],
        data_gaps=gaps,
    )
