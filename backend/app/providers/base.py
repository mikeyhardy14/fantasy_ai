from abc import ABC, abstractmethod

from app.domain.enums import Provider
from app.domain.provider_models import (
    ImportedLeagueSnapshot,
    LeagueDetails,
    LeagueSummary,
    MatchupData,
    PlayerData,
    ProviderCapabilities,
    ProviderState,
    ProviderUser,
    RosterData,
    TeamData,
    TransactionData,
)


class FantasyProvider(ABC):
    """Adapter contract for a fantasy football platform.

    Implementations translate platform payloads into the provider-neutral DTOs
    in app.domain.provider_models and raise app.core.errors.ProviderError
    subclasses on failure. They must not leak platform-specific structures.
    """

    provider: Provider
    capabilities: ProviderCapabilities

    @abstractmethod
    async def get_state(self) -> ProviderState:
        """Current NFL season + week according to the platform."""

    @abstractmethod
    async def get_user(self, identifier: str) -> ProviderUser:
        """Resolve a username / handle / id to a platform user."""

    @abstractmethod
    async def get_leagues(self, external_user_id: str, season: int) -> list[LeagueSummary]:
        ...

    @abstractmethod
    async def get_league(self, league_id: str) -> LeagueDetails:
        ...

    @abstractmethod
    async def get_teams(self, league_id: str) -> list[TeamData]:
        ...

    @abstractmethod
    async def get_rosters(self, league_id: str) -> list[RosterData]:
        ...

    @abstractmethod
    async def get_matchups(self, league_id: str, week: int) -> list[MatchupData]:
        ...

    @abstractmethod
    async def get_transactions(self, league_id: str, week: int) -> list[TransactionData]:
        ...

    @abstractmethod
    async def get_players(self) -> dict[str, PlayerData]:
        """Full player catalogue keyed by external player id."""

    @abstractmethod
    async def get_available_players(self, league_id: str) -> list[PlayerData]:
        ...

    async def fetch_league_snapshot(
        self, league_id: str, *, weeks_back: int = 3
    ) -> ImportedLeagueSnapshot:
        """Default implementation composed from the primitives above.

        Providers may override for efficiency. Matchups and transactions are
        fetched for the current week and a few prior weeks.
        """
        league = await self.get_league(league_id)
        teams = await self.get_teams(league_id)
        rosters = await self.get_rosters(league_id)
        players = await self.get_players()

        weeks = [w for w in range(league.current_week - weeks_back, league.current_week + 1) if w >= 1]
        matchups: list[MatchupData] = []
        transactions: list[TransactionData] = []
        for week in weeks:
            matchups.extend(await self.get_matchups(league_id, week))
            if self.capabilities.supports_transactions:
                transactions.extend(await self.get_transactions(league_id, week))

        return ImportedLeagueSnapshot(
            provider=self.provider,
            league=league,
            teams=teams,
            rosters=rosters,
            matchups=matchups,
            transactions=transactions,
            players=players,
        )
