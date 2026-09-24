from typing import Literal

from pydantic import BaseModel, Field

from app.domain.enums import Priority, RecommendationType
from app.domain.recommendation import Recommendation


class RecommendationOut(BaseModel):
    type: RecommendationType
    priority: Priority
    title: str
    reason: str
    players: list[str] = Field(default_factory=list)
    player_names: list[str] = Field(default_factory=list)
    position: str | None = None
    data: dict = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, rec: Recommendation) -> "RecommendationOut":
        return cls(**rec.model_dump())


# ---- Structured team analysis (strict schema for OpenAI structured output) -----


class LineupChange(BaseModel):
    slot: str = Field(description="Roster slot such as FLEX or RB")
    start_player: str = Field(description="Name of the player to start")
    sit_player: str | None = Field(default=None, description="Name of the player to bench, if any")
    reason: str


class WaiverPriority(BaseModel):
    position: str
    player_name: str | None = Field(default=None, description="Available player name, or null for a positional target")
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    reason: str


class TradeStrategy(BaseModel):
    can_trade_away: list[str] = Field(description="Positions with surplus")
    should_target: list[str] = Field(description="Positions to acquire")
    reasoning: str


class TeamAnalysis(BaseModel):
    """Structured 'Analyze My Team' output. Every claim must trace back to tool data."""

    team_summary: str
    strengths: list[str]
    weaknesses: list[str]
    lineup_changes: list[LineupChange]
    waiver_priorities: list[WaiverPriority]
    trade_strategy: TradeStrategy
    this_week: list[str] = Field(description="Most important actions before kickoff")
    data_gaps: list[str] = Field(
        default_factory=list,
        description="Information that was unavailable (e.g. projections) and therefore not used",
    )
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"


GeneratedBy = Literal["openai", "gemini", "groq", "deterministic"]


class TeamAnalysisResponse(BaseModel):
    analysis: TeamAnalysis
    recommendations: list[RecommendationOut]
    generated_by: GeneratedBy
    model: str | None = None
    tools_used: list[str] = Field(default_factory=list)


# ---- Chat ---------------------------------------------------------------------


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    messages: list[ChatMessageIn] = Field(min_length=1, max_length=40)
    week: int | None = Field(default=None, ge=1, le=18)


class ChatResponse(BaseModel):
    message: str
    tools_used: list[str] = Field(default_factory=list)
    generated_by: GeneratedBy
    suggested_questions: list[str] = Field(default_factory=list)


# ---- Trade -------------------------------------------------------------------


class TradeAnalysisRequest(BaseModel):
    give: list[str] = Field(min_length=1, max_length=6, description="Internal player ids you send")
    receive: list[str] = Field(min_length=1, max_length=6, description="Internal player ids you get")
    partner_team_id: str | None = None


class TradeSideSummary(BaseModel):
    players: list[str]
    positions: list[str]
    projected_points: float | None
    injured: list[str]


class TradeAnalysis(BaseModel):
    verdict: Literal["ACCEPT", "REJECT", "NEGOTIATE", "UNCLEAR"]
    summary: str
    you_give: TradeSideSummary
    you_receive: TradeSideSummary
    roster_impact: list[str]
    lineup_impact: list[str]
    risks: list[str]
    data_gaps: list[str] = Field(default_factory=list)


class TradeAnalysisResponse(BaseModel):
    analysis: TradeAnalysis
    generated_by: GeneratedBy


# ---- Weekly briefing --------------------------------------------------------


class BriefingItem(BaseModel):
    title: str
    detail: str
    priority: Priority
    type: RecommendationType | None = None


class PositionAssessment(BaseModel):
    position: str
    grade: str


class WeeklyBriefing(BaseModel):
    week: int
    team_name: str
    record: str
    opponent_name: str | None
    projected_user: float | None
    projected_opponent: float | None
    attention_items: list[BriefingItem]
    recommended_actions: list[str]
    waiver_targets: list[str]
    roster_assessment: list[PositionAssessment]
    narrative: str | None = None
    generated_by: GeneratedBy
