from fastapi import APIRouter

from app.api.deps import AI, ToolCtx
from app.schemas.ai import (
    ChatRequest,
    ChatResponse,
    TeamAnalysisResponse,
    SuggestTradeRequest,
    SuggestTradeResponse,
    CompareTeamsRequest,
    CompareTeamsResponse,
    TradeAnalysisRequest,
    TradeAnalysisResponse,
    TradeReviewRequest,
    TradeReviewResponse,
    WaiverSuggestionsResponse,
)

router = APIRouter(prefix="/leagues/{league_id}/ai", tags=["ai"])


@router.post("/analyze", response_model=TeamAnalysisResponse)
async def analyze_team(tool_ctx: ToolCtx, ai: AI) -> TeamAnalysisResponse:
    return await ai.analyze_team(tool_ctx)


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, tool_ctx: ToolCtx, ai: AI) -> ChatResponse:
    if body.week:
        tool_ctx.week = body.week
        tool_ctx.invalidate()
    tool_ctx.auto_approve = body.auto_approve
    return await ai.chat(tool_ctx, body.messages)


@router.post("/compare", response_model=CompareTeamsResponse)
async def compare_teams(body: CompareTeamsRequest, tool_ctx: ToolCtx, ai: AI) -> CompareTeamsResponse:
    return await ai.compare_teams(tool_ctx, body.team_ids, body.week)


@router.post("/waivers", response_model=WaiverSuggestionsResponse)
async def waiver_suggestions(tool_ctx: ToolCtx, ai: AI) -> WaiverSuggestionsResponse:
    return await ai.suggest_waivers(tool_ctx)


@router.post("/trade", response_model=TradeAnalysisResponse)
async def analyze_trade(body: TradeAnalysisRequest, tool_ctx: ToolCtx, ai: AI) -> TradeAnalysisResponse:
    return await ai.analyze_trade(tool_ctx, body)


@router.post("/trade/for", response_model=SuggestTradeResponse)
async def suggest_trade(body: SuggestTradeRequest, tool_ctx: ToolCtx, ai: AI) -> SuggestTradeResponse:
    return await ai.suggest_trade_for(tool_ctx, body.player_id)


@router.post("/trade/review", response_model=TradeReviewResponse)
async def review_trade(body: TradeReviewRequest, tool_ctx: ToolCtx, ai: AI) -> TradeReviewResponse:
    return await ai.review_trade(tool_ctx, body.transaction_id)
