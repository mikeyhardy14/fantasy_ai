"""AI use cases: analysis, chat, trade evaluation, briefing narrative.

Chooses between the OpenAI-backed agent and deterministic fallbacks based on
configuration. Never touches provider-specific data.
"""

from __future__ import annotations

from uuid import UUID

from app.ai import fallback, prompts
from app.ai.agent import Agent
from app.ai.approvals import swaps_mentioned
from app.ai.llm import LLMClient
from app.ai.subs import sub_proposal
from app.ai.tools import ToolContext, league_tool_registry
from app.ai.tools.base import ToolRegistry
from app.ai.trade_review import (
    exchanges,
    format_review,
    is_trade_review,
    other_teams,
    player_ids,
    reviewable,
    score_exchange,
    user_exchange,
)
from app.core.errors import AppError, NotFoundError, ValidationFailed
from app.core.logging import get_logger
from app.intelligence.briefing import build_briefing
from app.intelligence.recommendations import generate_recommendations
from app.schemas.ai import (
    ChatMessageIn,
    ChatResponse,
    RecommendationOut,
    TeamAnalysis,
    TeamAnalysisResponse,
    TradeAnalysis,
    TradeAnalysisRequest,
    TradeAnalysisResponse,
    TradeReviewResponse,
    WaiverSuggestionsResponse,
    WeeklyBriefing,
)
from app.schemas.league import PlayerOut, TransactionOut

log = get_logger(__name__)

SUGGESTED = [
    "Who should I start at FLEX?",
    "What are the biggest weaknesses on my roster?",
    "What position should I target on waivers?",
    "Which bench player has the most upside?",
    "How should I prepare for next week?",
    "Set this week's lineup",
]


class AIService:
    def __init__(self, llm: LLMClient | None, max_tool_rounds: int = 8):
        self.llm = llm
        self.max_tool_rounds = max_tool_rounds

    @property
    def enabled(self) -> bool:
        return self.llm is not None

    def _generated_by(self) -> str:
        provider = getattr(self.llm, "provider", "openai")
        return provider if provider in {"openai", "gemini", "groq"} else "openai"

    def _agent(self) -> Agent:
        assert self.llm is not None
        return Agent(self.llm, league_tool_registry, max_rounds=self.max_tool_rounds)

    def _advice_agent(self) -> Agent:
        """Same tools as chat, without the lineup writes."""
        assert self.llm is not None
        registry = ToolRegistry()
        for tool in league_tool_registry.tools.values():
            if tool.name not in {"change_lineup", "set_lineup", "claim_player"}:
                registry.register(tool)
        return Agent(self.llm, registry, max_rounds=self.max_tool_rounds)

    async def _system(self, ctx: ToolContext) -> dict:
        tc = await ctx.team_context()
        return {
            "role": "system",
            "content": prompts.SYSTEM_BASE.format(
                league_name=tc.league_name,
                season=tc.season,
                week=tc.week,
                scoring_type=tc.scoring_type,
                team_name=tc.team.team.name,
                record=tc.team.team.record,
            ),
        }

    # ---- Analyze my team ---------------------------------------------------------

    async def analyze_team(self, ctx: ToolContext) -> TeamAnalysisResponse:
        tc = await ctx.team_context()
        recs = generate_recommendations(tc)
        rec_out = [RecommendationOut.from_domain(r) for r in recs]
        if not self.enabled:
            analysis = fallback.deterministic_analysis(tc, recs)
            return TeamAnalysisResponse(analysis=analysis, recommendations=rec_out, generated_by="deterministic")

        messages = [await self._system(ctx), {"role": "user", "content": prompts.ANALYSIS_INSTRUCTIONS}]
        result = await self._agent().run(messages, ctx, response_model=TeamAnalysis, temperature=0.2)
        assert isinstance(result.structured, TeamAnalysis)
        analysis = fallback.omit_false_season_gap(result.structured, tc)
        return TeamAnalysisResponse(
            analysis=analysis,
            recommendations=rec_out,
            generated_by=self._generated_by(),
            model=result.model,
            tools_used=sorted(set(result.tools_used)),
        )

    # ---- Chat --------------------------------------------------------------------

    async def chat(self, ctx: ToolContext, history: list[ChatMessageIn]) -> ChatResponse:
        if history[-1].role != "user":
            raise ValidationFailed("The last message must be from the user.")
        tc = await ctx.team_context()
        proposal = sub_proposal(tc.team, tc.week, history[-1].content)
        if proposal is not None:
            message, actions = proposal
            return ChatResponse(
                message=message,
                tools_used=["get_roster"],
                generated_by="deterministic",
                suggested_questions=SUGGESTED[:3],
                actions=actions,
            )
        if is_trade_review(history[-1].content):
            return ChatResponse(
                message=await self.made_trades_message(ctx),
                tools_used=["get_recent_transactions"],
                generated_by="deterministic",
                suggested_questions=SUGGESTED[:3],
            )
        if not self.enabled:
            recs = generate_recommendations(tc)
            response = fallback.deterministic_chat(tc, recs, history[-1].content)
            response.actions = swaps_mentioned(tc.team, tc.week, response.message)
            return response

        messages = [await self._system(ctx), {"role": "system", "content": prompts.CHAT_INSTRUCTIONS}]
        messages += [{"role": m.role, "content": m.content} for m in history[-20:]]
        result = await self._agent().run(messages, ctx, temperature=0.4)
        message = result.content or "I could not produce an answer. Please try rephrasing."
        wrote = {"change_lineup", "set_lineup"} & set(result.tools_used)
        actions = list(ctx.pending_lineups)
        if not wrote:
            actions.extend(swaps_mentioned(tc.team, tc.week, message))
        return ChatResponse(
            message=message,
            tools_used=sorted(set(result.tools_used)),
            generated_by=self._generated_by(),
            suggested_questions=SUGGESTED[:3],
            actions=actions,
            claims=list(ctx.pending_claims),
        )

    # ---- Waivers --------------------------------------------------------------------

    async def suggest_waivers(self, ctx: ToolContext) -> WaiverSuggestionsResponse:
        tc = await ctx.team_context()
        recs = generate_recommendations(tc)
        if not self.enabled:
            return WaiverSuggestionsResponse(message=fallback.deterministic_waivers(tc, recs), generated_by="deterministic")

        messages = [await self._system(ctx), {"role": "user", "content": prompts.WAIVER_INSTRUCTIONS}]
        try:
            result = await self._advice_agent().run(messages, ctx, temperature=0.3)
        except AppError as exc:
            log.warning("ai.waivers_failed", error=exc.message)
            return WaiverSuggestionsResponse(message=fallback.deterministic_waivers(tc, recs), generated_by="deterministic")
        return WaiverSuggestionsResponse(
            message=result.content or fallback.deterministic_waivers(tc, recs),
            generated_by=self._generated_by() if result.content else "deterministic",
            model=result.model,
            tools_used=sorted(set(result.tools_used)),
        )

    # ---- Trade --------------------------------------------------------------------

    async def analyze_trade(self, ctx: ToolContext, req: TradeAnalysisRequest) -> TradeAnalysisResponse:
        tc = await ctx.team_context()
        give = [await ctx.service.get_player_in_league(ctx.league, _uuid(pid), ctx.week) for pid in req.give]
        receive = [await ctx.service.get_player_in_league(ctx.league, _uuid(pid), ctx.week) for pid in req.receive]
        roster_ids = {s.player.id for s in tc.all_roster if s.player}
        not_owned = [p.name for p in give if p.id not in roster_ids]
        if not_owned:
            raise ValidationFailed(f"You can only trade away players on your roster: {', '.join(not_owned)}.")
        owned_receive = [p.name for p in receive if p.id in roster_ids]
        if owned_receive:
            raise ValidationFailed(f"You already roster: {', '.join(owned_receive)}.")

        base = fallback.deterministic_trade(tc, give, receive)
        if not self.enabled:
            return TradeAnalysisResponse(analysis=base, generated_by="deterministic")

        facts = {
            "deterministic_assessment": base.model_dump(mode="json"),
            "roster_needs": tc.needs.model_dump(mode="json"),
            "give": [p.model_dump(mode="json", exclude={"external_ids"}) for p in give],
            "receive": [p.model_dump(mode="json", exclude={"external_ids"}) for p in receive],
            "lineup_slots": tc.lineup_slots,
            "scoring_type": tc.scoring_type,
        }
        messages = [
            await self._system(ctx),
            {"role": "system", "content": prompts.TRADE_INSTRUCTIONS},
            {"role": "user", "content": f"Trade facts:\n{facts}"},
        ]
        result = await self._agent().run(messages, ctx, response_model=TradeAnalysis, temperature=0.2)
        assert isinstance(result.structured, TradeAnalysis)
        return TradeAnalysisResponse(analysis=result.structured, generated_by=self._generated_by())

    async def made_trades_message(self, ctx: ToolContext) -> str:
        trades = reviewable(await ctx.service.league_trades(ctx.league))
        if not trades:
            return "No completed trades are in this league's record."
        reviews = [await self.review_trade(ctx, trade.id, use_model=False) for trade in trades[:6]]
        lines = [format_review(review) for review in reviews]
        if len(trades) > 6:
            lines.append("Older trades are on the Trades page.")
        return "\n\n".join(lines)

    async def review_trade(self, ctx: ToolContext, transaction_id: UUID, *, use_model: bool = True) -> TradeReviewResponse:
        trade = await ctx.service.get_trade(ctx.league, transaction_id)
        user = await ctx.service.user_team(ctx.league)
        rows = exchanges(trade.adds, trade.drops)
        mine = user_exchange(rows, str(user.id) if user else None)
        actor = mine or (rows[0] if rows else None)
        if actor is None or not player_ids(actor.sent) or not player_ids(actor.received):
            raise ValidationFailed("That trade does not have players on both sides to review.")
        give = await self._trade_players(ctx, player_ids(actor.sent))
        receive = await self._trade_players(ctx, player_ids(actor.received))
        yours = mine is not None
        analysis = score_exchange(
            actor=actor.team_name,
            other=other_teams(rows, actor),
            give=give,
            receive=receive,
            picks=trade.picks,
            yours=yours,
            already_done=trade.status == "complete",
        )
        generated_by = "deterministic"
        if use_model and self.enabled:
            drafted = await self._narrate_trade(ctx, trade, analysis, yours)
            if drafted is not None:
                analysis = drafted
                generated_by = self._generated_by()
        return TradeReviewResponse(
            transaction_id=trade.id,
            week=trade.week,
            status=trade.status,
            teams=trade.team_names,
            involves_user=yours,
            perspective=actor.team_name,
            picks=trade.picks,
            analysis=analysis,
            generated_by=generated_by,
        )

    async def _trade_players(self, ctx: ToolContext, ids: list[str]) -> list[PlayerOut]:
        players: list[PlayerOut] = []
        for pid in ids:
            try:
                players.append(await ctx.service.get_player_in_league(ctx.league, _uuid(pid), ctx.week))
            except NotFoundError as exc:
                raise ValidationFailed("A player in that trade is no longer in the league pool.") from exc
        return players

    async def _narrate_trade(
        self, ctx: ToolContext, trade: TransactionOut, analysis: TradeAnalysis, yours: bool
    ) -> TradeAnalysis | None:
        if yours:
            role = "This trade included the user's roster."
        else:
            role = "The user's roster was not in this trade. Judge the named team, not the user."
        facts = {
            "status": trade.status,
            "week": trade.week,
            "teams": trade.team_names,
            "picks": trade.picks,
            "assessment": analysis.model_dump(mode="json"),
            "instruction": (
                f"{role} The trade is already {trade.status}. Use only the assessment facts. "
                "Do not tell anyone to submit, accept, or reject it in Sleeper. "
                "ACCEPT means the receiving side gained projected points, REJECT means they gave them up, "
                "NEGOTIATE means the sides are close, UNCLEAR means a projection is missing."
            ),
        }
        try:
            assert self.llm is not None
            resp = await self.llm.complete(
                [
                    await self._system(ctx),
                    {"role": "system", "content": prompts.TRADE_REVIEW_INSTRUCTIONS},
                    {"role": "user", "content": f"Completed trade facts:\n{facts}"},
                ],
                response_model=TradeAnalysis,
                temperature=0.2,
            )
            return TradeAnalysis.model_validate_json(resp.content or "")
        except Exception as exc:  # noqa: BLE001 - the scored review still stands
            log.warning("ai.trade_review_failed", error=str(exc))
            return None

    # ---- Briefing -------------------------------------------------------------------

    async def weekly_briefing(self, ctx: ToolContext) -> WeeklyBriefing:
        tc = await ctx.team_context()
        recs = generate_recommendations(tc)
        briefing = build_briefing(tc, recs)
        if not self.enabled:
            return briefing
        try:
            assert self.llm is not None
            resp = await self.llm.complete(
                [
                    await self._system(ctx),
                    {"role": "system", "content": prompts.BRIEFING_NARRATIVE_INSTRUCTIONS},
                    {"role": "user", "content": briefing.model_dump_json(exclude={"narrative", "generated_by"})},
                ],
                temperature=0.4,
            )
            briefing.narrative = (resp.content or "").strip() or None
            briefing.generated_by = self._generated_by()
        except Exception as exc:  # noqa: BLE001 - narrative is optional
            log.warning("ai.briefing_narrative_failed", error=str(exc))
        return briefing


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValidationFailed(f"Invalid player id: {value}") from exc
