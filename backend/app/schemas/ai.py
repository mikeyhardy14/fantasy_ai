from typing import Literal
from uuid import UUID

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
    auto_approve: bool = False


class LineupAction(BaseModel):
    """A lineup move the chat can run after the manager approves it."""

    label: str
    summary: str = ""
    player_id: UUID
    player_name: str
    position: str | None = None
    headshot_url: str | None = None
    destination: Literal["starter", "bench", "ir"] = "starter"
    slot_index: int | None = None
    slot: str
    week: int
    replaces: str | None = None
    detail: str | None = None


class RosterClaim(BaseModel):
    """An add, a drop, or both. Nothing is written until the manager approves it."""

    summary: str
    add_player_id: UUID | None = None
    add_player_name: str | None = None
    add_position: str | None = None
    add_headshot_url: str | None = None
    drop_player_id: UUID | None = None
    drop_player_name: str | None = None
    drop_position: str | None = None
    detail: str | None = None


class ChatResponse(BaseModel):
    message: str
    tools_used: list[str] = Field(default_factory=list)
    generated_by: GeneratedBy
    suggested_questions: list[str] = Field(default_factory=list)
    actions: list[LineupAction] = Field(default_factory=list)
    claims: list[RosterClaim] = Field(default_factory=list)


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


class SuggestTradeRequest(BaseModel):
    player_id: UUID


class TradeSidePlayer(BaseModel):
    id: UUID
    name: str
    position: str | None = None


class SuggestTradeResponse(BaseModel):
    give: list[TradeSidePlayer]
    receive: list[TradeSidePlayer]
    opponent_name: str
    message: str
    generated_by: GeneratedBy


class TradeDraft(BaseModel):
    """Structured choice from the model. Ids must come from the user's roster."""

    give_player_ids: list[str] = Field(min_length=1, max_length=2)
    message: str = Field(min_length=1, max_length=400)


class TradeReviewRequest(BaseModel):
    transaction_id: UUID


class TradeReviewResponse(BaseModel):
    transaction_id: UUID
    week: int | None
    status: str
    teams: list[str]
    involves_user: bool
    perspective: str
    picks: list[str] = Field(default_factory=list)
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


class WaiverSuggestionsResponse(BaseModel):
    message: str
    generated_by: GeneratedBy
    model: str | None = None
    tools_used: list[str] = Field(default_factory=list)


class CompareTeamsRequest(BaseModel):
    team_ids: list[UUID] = Field(min_length=2, max_length=2)
    week: int | None = Field(default=None, ge=1, le=18)


class CompareStarter(BaseModel):
    name: str
    slot: str
    position: str | None = None
    projected_points: float | None = None
    points: float | None = None
    injury_status: str | None = None
    on_bye: bool = False


class ComparePosition(BaseModel):
    position: str
    grade: str
    healthy_depth: int
    total_depth: int
    starter_projection: float | None = None


class CompareSide(BaseModel):
    team_id: UUID
    name: str
    owner_name: str | None = None
    is_user_team: bool = False
    record: str
    points_for: float
    points_against: float
    projected_points: float | None = None
    faab_remaining: int | None = None
    waiver_position: int | None = None
    starters_out: int = 0
    starters_on_bye: int = 0
    positions: list[ComparePosition] = Field(default_factory=list)
    starters: list[CompareStarter] = Field(default_factory=list)


class CompareTeamsResponse(BaseModel):
    week: int
    sides: list[CompareSide]
    summary: str
    generated_by: GeneratedBy
    model: str | None = None
