"""AI use cases: analysis, chat, trade evaluation, briefing narrative.

Chooses between the OpenAI-backed agent and deterministic fallbacks based on
configuration. Never touches provider-specific data.
"""

from __future__ import annotations

from uuid import UUID

from app.ai import fallback, prompts
from app.ai.agent import Agent
from app.ai.llm import LLMClient
from app.ai.tools import ToolContext, league_tool_registry
from app.core.errors import ValidationFailed
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
    WeeklyBriefing,
)

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
        return TeamAnalysisResponse(
            analysis=result.structured,
            recommendations=rec_out,
            generated_by=self._generated_by(),
            model=result.model,
            tools_used=sorted(set(result.tools_used)),
        )

    # ---- Chat --------------------------------------------------------------------

    async def chat(self, ctx: ToolContext, history: list[ChatMessageIn]) -> ChatResponse:
        if history[-1].role != "user":
            raise ValidationFailed("The last message must be from the user.")
        if not self.enabled:
            tc = await ctx.team_context()
            recs = generate_recommendations(tc)
            return fallback.deterministic_chat(tc, recs, history[-1].content)

        messages = [await self._system(ctx), {"role": "system", "content": prompts.CHAT_INSTRUCTIONS}]
        messages += [{"role": m.role, "content": m.content} for m in history[-20:]]
        result = await self._agent().run(messages, ctx, temperature=0.4)
        return ChatResponse(
            message=result.content or "I could not produce an answer. Please try rephrasing.",
            tools_used=sorted(set(result.tools_used)),
            generated_by=self._generated_by(),
            suggested_questions=SUGGESTED[:3],
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
