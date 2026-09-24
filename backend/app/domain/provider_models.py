"""Provider-neutral data transfer objects.

Every FantasyProvider adapter converts its platform's payloads into these
shapes. Nothing outside app/providers/<name> should ever see raw platform JSON.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import Provider


class ProviderCapabilities(BaseModel):
    auth_type: str  # "username" | "oauth" | "cookie"
    supports_available_players: bool = True
    supports_transactions: bool = True
    supports_projections: bool = False
    supports_faab: bool = True


class ProviderState(BaseModel):
    season: int
    week: int
    season_type: str = "regular"


class ProviderUser(BaseModel):
    external_user_id: str
    username: str
    display_name: str | None = None
    avatar: str | None = None


class LeagueSummary(BaseModel):
    external_league_id: str
    name: str
    season: int
    team_count: int
    status: str | None = None
    avatar: str | None = None
    scoring_type: str | None = None  # e.g. "PPR", "Half PPR", "Standard"


class LeagueDetails(BaseModel):
    external_league_id: str
    name: str
    season: int
    team_count: int
    current_week: int
    status: str | None = None
    avatar: str | None = None
    scoring_settings: dict[str, float] = Field(default_factory=dict)
    roster_positions: list[str] = Field(default_factory=list)
    roster_settings: dict[str, Any] = Field(default_factory=dict)
    league_settings: dict[str, Any] = Field(default_factory=dict)


class TeamData(BaseModel):
    external_team_id: str
    owner_external_id: str | None = None
    owner_name: str | None = None
    name: str
    avatar: str | None = None
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: float = 0.0
    points_against: float = 0.0
    faab_remaining: int | None = None
    waiver_position: int | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class RosterSlotEntry(BaseModel):
    external_player_id: str
    roster_slot: str
    is_starter: bool
    slot_index: int | None = None


class RosterData(BaseModel):
    external_team_id: str
    entries: list[RosterSlotEntry]


class MatchupData(BaseModel):
    external_matchup_id: str | None
    week: int
    external_team_id: str
    points: float = 0.0
    projected_points: float | None = None
    player_points: dict[str, float] = Field(default_factory=dict)  # external_player_id -> pts


class TransactionData(BaseModel):
    external_transaction_id: str
    type: str
    status: str
    week: int | None
    created_at: datetime
    adds: list[dict[str, str]] = Field(default_factory=list)  # {external_player_id, external_team_id}
    drops: list[dict[str, str]] = Field(default_factory=list)
    external_team_ids: list[str] = Field(default_factory=list)
    faab_bid: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlayerData(BaseModel):
    external_player_id: str
    name: str
    first_name: str | None = None
    last_name: str | None = None
    position: str | None = None
    fantasy_positions: list[str] = Field(default_factory=list)
    nfl_team: str | None = None
    status: str | None = None
    injury_status: str | None = None
    injury_body_part: str | None = None
    age: int | None = None
    years_exp: int | None = None
    number: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_fantasy_relevant(self) -> bool:
        from app.domain.enums import FANTASY_POSITIONS

        return bool(self.position in FANTASY_POSITIONS and self.nfl_team)


class ImportedLeagueSnapshot(BaseModel):
    """Everything a provider knows about a league, fetched in one pass."""

    provider: Provider
    league: LeagueDetails
    teams: list[TeamData]
    rosters: list[RosterData]
    matchups: list[MatchupData]
    transactions: list[TransactionData]
    players: dict[str, PlayerData]  # keyed by external_player_id
