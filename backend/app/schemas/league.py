from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.nfl_data.base import ScheduleGame
from app.nfl_data.sleeper_stats import RecentGame


class FantasyAccountOut(BaseModel):
    id: UUID
    provider: str
    external_user_id: str
    username: str
    display_name: str | None = None
    avatar: str | None = None
    created_at: datetime
    last_synced_at: datetime | None = None
    writes_enabled: bool = False

    model_config = {"from_attributes": True}


def fantasy_account_out(account: Any) -> FantasyAccountOut:
    """Serialize an account without ever exposing stored credentials."""
    return FantasyAccountOut.model_validate(account).model_copy(
        update={"writes_enabled": bool(getattr(account, "encrypted_credentials", None))}
    )


class ConnectRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$")


class ProviderLeagueOut(BaseModel):
    external_league_id: str
    name: str
    season: int
    team_count: int
    status: str | None = None
    avatar: str | None = None
    scoring_type: str | None = None
    imported: bool = False


class ProviderLeaguesResponse(BaseModel):
    account: FantasyAccountOut
    season: int
    leagues: list[ProviderLeagueOut]


class LeagueOut(BaseModel):
    id: UUID
    provider: str
    external_league_id: str
    name: str
    season: int
    team_count: int
    current_week: int
    status: str | None = None
    avatar: str | None = None
    scoring_type: str | None = None
    last_synced_at: datetime | None = None
    sync_status: str
    sync_error: str | None = None
    user_team_id: UUID | None = None
    user_team_name: str | None = None

    model_config = {"from_attributes": True}


class LeagueDetailOut(LeagueOut):
    scoring_settings: dict[str, float]
    roster_settings: dict[str, Any]
    league_settings: dict[str, Any]
    account: FantasyAccountOut


class PropLineOut(BaseModel):
    label: str
    line: float
    weight: float
    points: float
    odds: str | None = None
    probability: float | None = None


class PlayerOut(BaseModel):
    id: UUID
    name: str
    position: str | None
    fantasy_positions: list[str] = Field(default_factory=list)
    nfl_team: str | None
    status: str | None = None
    injury_status: str | None = None
    injury_body_part: str | None = None
    age: int | None = None
    years_exp: int | None = None
    bye_week: int | None = None
    on_bye: bool = False
    opponent: str | None = None
    projected_points: float | None = None
    projection_note: str | None = None
    projection_detail: dict[str, float] = Field(default_factory=dict)
    season_points: float | None = None
    points_per_game: float | None = None
    headshot_url: str | None = None
    schedule: list[ScheduleGame] = Field(default_factory=list)
    projection_reasons: list[str] = Field(default_factory=list)
    projection_lines: list[PropLineOut] = Field(default_factory=list)
    external_ids: dict[str, str] = Field(default_factory=dict)


class PlayerSheetOut(BaseModel):
    player: PlayerOut
    recent_games: list[RecentGame] = Field(default_factory=list)
    games_note: str | None = None


class RosterSlotOut(BaseModel):
    slot: str
    slot_index: int | None = None
    is_starter: bool
    player: PlayerOut | None
    points: float | None = None  # actual points this week when known
    stat_line: str | None = None  # counting stats while that player's game is on
    flags: list[str] = Field(default_factory=list)  # e.g. "INJURED", "BYE", "OUT"


class TeamSummaryOut(BaseModel):
    id: UUID
    name: str
    owner_name: str | None = None
    avatar: str | None = None
    wins: int
    losses: int
    ties: int
    record: str
    points_for: float
    points_against: float
    faab_remaining: int | None = None
    waiver_position: int | None = None
    is_user_team: bool = False


class TeamOut(BaseModel):
    team: TeamSummaryOut
    week: int
    starters: list[RosterSlotOut]
    bench: list[RosterSlotOut]
    reserve: list[RosterSlotOut]
    lineup_slots: list[str]
    lineup_issues: list[str]
    projected_points: float | None = None
    projection_coverage: str  # "full" | "partial" | "none"


class LineupUpdateRequest(BaseModel):
    week: int = Field(ge=1, le=18)
    starter_player_ids: list[UUID | None] = Field(min_length=1, max_length=20)


class AddPlayerRequest(BaseModel):
    player_id: UUID | None = None
    drop_player_id: UUID | None = None

    @model_validator(mode="after")
    def require_add_or_drop(self):
        if self.player_id is None and self.drop_player_id is None:
            raise ValueError("Choose a player to add or a player to drop.")
        return self


class ProposeTradeRequest(BaseModel):
    give: list[UUID] = Field(min_length=1, max_length=6)
    receive: list[UUID] = Field(min_length=1, max_length=6)


class ProposeTradeResponse(BaseModel):
    message: str
    status: str
    transaction_id: str | None = None
    opponent_name: str


class RosterMoveRequest(BaseModel):
    week: int = Field(ge=1, le=18)
    player_id: UUID
    destination: Literal["starter", "bench", "ir"]
    slot_index: int | None = Field(default=None, ge=0, le=19)


class SleeperTokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=4000)


class LineupUpdateResponse(BaseModel):
    team: TeamOut
    verified: bool | None
    public_api_confirmed: bool | None
    message: str


class MatchupSideOut(BaseModel):
    team: TeamSummaryOut
    points: float
    projected_points: float | None
    starters: list[RosterSlotOut]


class SlotCallOut(BaseModel):
    slot_index: int
    start_name: str
    win_prob: float
    confidence: str


class NflGameOut(BaseModel):
    away: str
    home: str
    away_score: int | None = None
    home_score: int | None = None
    state: str | None = None
    detail: str | None = None
    summary: str | None = None
    broadcast: str | None = None


class MatchupOut(BaseModel):
    week: int
    is_bye: bool
    user: MatchupSideOut
    opponent: MatchupSideOut | None
    status: str  # "upcoming" | "in_progress" | "final" | "bye"
    calls: list[SlotCallOut] = Field(default_factory=list)
    games: list[NflGameOut] = Field(default_factory=list)


class LeagueMatchupOut(BaseModel):
    week: int
    is_bye: bool
    involves_user: bool
    status: str
    team: MatchupSideOut
    opponent: MatchupSideOut | None


class StandingsRowOut(TeamSummaryOut):
    rank: int
    streak: str | None = None


class TransactionOut(BaseModel):
    id: UUID
    type: str
    status: str
    week: int | None
    created_at: datetime
    adds: list[dict[str, Any]]
    drops: list[dict[str, Any]]
    team_names: list[str]
    faab_bid: int | None = None
    involves_user: bool = False
    picks: list[str] = Field(default_factory=list)


class PositionNeedOut(BaseModel):
    position: str
    required_starters: int
    healthy_starters: int
    total_depth: int
    healthy_depth: int
    grade: str  # Strong | Adequate | Needs depth | Weak
    notes: list[str] = Field(default_factory=list)


class RosterNeedsOut(BaseModel):
    positions: list[PositionNeedOut]
    weakest_positions: list[str]
    strongest_positions: list[str]
    surplus_positions: list[str]
    open_roster_spots: int
    roster_size: int
    max_roster_size: int | None


class SyncResponse(BaseModel):
    league: LeagueOut
    message: str


class RankingRowOut(BaseModel):
    rank: int
    player_id: UUID
    name: str
    position: str | None = None
    nfl_team: str | None = None
    opponent: str | None = None
    home: bool | None = None
    headshot_url: str | None = None
    injury_status: str | None = None
    total: float | None = None
    spread: float | None = None
    implied_points: float | None = None
    win_probability: float | None = None
    book_count: int = 0
    books: list[str] = Field(default_factory=list)
    projected_points: float | None = None
    projection_source: str | None = None
    season_points: float | None = None
    vorp: float | None = None
    owned: Literal["you", "league"] | None = None


class RankingsOut(BaseModel):
    week: int
    notes: list[str] = []
    truncated: bool = False
    rows: list[RankingRowOut]
