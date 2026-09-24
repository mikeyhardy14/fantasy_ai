from dataclasses import dataclass, field

from app.schemas.league import (
    MatchupOut,
    PlayerOut,
    RosterNeedsOut,
    StandingsRowOut,
    TeamOut,
    TransactionOut,
)


@dataclass
class TeamContext:
    """Everything the deterministic engine (and AI tools) need about one team.

    Built by app.services.league_context.LeagueContextService from the
    normalized DB plus the NFLDataProvider. Contains no provider-specific data.
    """

    league_id: str
    league_name: str
    season: int
    week: int
    scoring_type: str
    scoring_settings: dict[str, float]
    lineup_slots: list[str]
    waiver_type: str | None
    team: TeamOut
    matchup: MatchupOut | None
    needs: RosterNeedsOut
    available: list[PlayerOut] = field(default_factory=list)
    recent_transactions: list[TransactionOut] = field(default_factory=list)
    standings: list[StandingsRowOut] = field(default_factory=list)
    projections_available: bool = False
    bye_weeks_available: bool = False

    @property
    def all_roster(self):
        return self.team.starters + self.team.bench + self.team.reserve

    def available_at(self, position: str, limit: int = 5) -> list[PlayerOut]:
        pool = [p for p in self.available if p.position == position and not p.injury_status]
        pool.sort(
            key=lambda p: (
                p.projected_points is None,
                -(p.projected_points or 0.0),
                p.points_per_game is None,
                -(p.points_per_game or 0.0),
                p.name,
            )
        )
        return pool[:limit]
