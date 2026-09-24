from fastapi import APIRouter

from app.api.deps import AI, ToolCtx
from app.schemas.ai import (
    ChatRequest,
    ChatResponse,
    TeamAnalysisResponse,
    TradeAnalysisRequest,
    TradeAnalysisResponse,
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
    return await ai.chat(tool_ctx, body.messages)


@router.post("/trade", response_model=TradeAnalysisResponse)
async def analyze_trade(body: TradeAnalysisRequest, tool_ctx: ToolCtx, ai: AI) -> TradeAnalysisResponse:
    return await ai.analyze_trade(tool_ctx, body)
