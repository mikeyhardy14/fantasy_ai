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
from app.providers.base import FantasyProvider
from app.providers.sleeper import mappers
from app.providers.sleeper.client import SleeperClient


class SleeperProvider(FantasyProvider):
    provider = Provider.SLEEPER
    capabilities = ProviderCapabilities(
        auth_type="username",
        supports_available_players=True,
        supports_transactions=True,
        supports_projections=False,
        supports_faab=True,
    )

    def __init__(self, client: SleeperClient):
        self.client = client

    async def get_state(self) -> ProviderState:
        return mappers.map_state(await self.client.get_state())

    async def get_user(self, identifier: str) -> ProviderUser:
        return mappers.map_user(await self.client.get_user(identifier.strip()))

    async def get_leagues(self, external_user_id: str, season: int) -> list[LeagueSummary]:
        raw = await self.client.get_user_leagues(external_user_id, season)
        return [mappers.map_league_summary(item) for item in raw]

    async def get_league(self, league_id: str) -> LeagueDetails:
        raw = await self.client.get_league(league_id)
        fallback_week = None
        if not (raw.get("settings") or {}).get("leg"):
            fallback_week = (await self.get_state()).week
        return mappers.map_league_details(raw, fallback_week=fallback_week)

    async def get_teams(self, league_id: str) -> list[TeamData]:
        league = await self.client.get_league(league_id)
        rosters = await self.client.get_rosters(league_id)
        users = await self.client.get_league_users(league_id)
        budget = (league.get("settings") or {}).get("waiver_budget")
        return mappers.map_teams(rosters, users, budget)

    async def get_rosters(self, league_id: str) -> list[RosterData]:
        league = await self.client.get_league(league_id)
        rosters = await self.client.get_rosters(league_id)
        positions = [str(p) for p in league.get("roster_positions") or []]
        return [mappers.map_roster(r, positions) for r in rosters]

    async def get_matchups(self, league_id: str, week: int) -> list[MatchupData]:
        raw = await self.client.get_matchups(league_id, week)
        return [mappers.map_matchup(m, week) for m in raw]

    async def get_transactions(self, league_id: str, week: int) -> list[TransactionData]:
        raw = await self.client.get_transactions(league_id, week)
        return [mappers.map_transaction(t) for t in raw]

    async def get_players(self) -> dict[str, PlayerData]:
        raw = await self.client.get_players()
        return {pid: mappers.map_player(pid, data) for pid, data in raw.items() if isinstance(data, dict)}

    async def get_available_players(self, league_id: str) -> list[PlayerData]:
        rosters = await self.client.get_rosters(league_id)
        rostered = {str(p) for r in rosters for p in (r.get("players") or [])}
        players = await self.get_players()
        return [p for pid, p in players.items() if pid not in rostered and p.is_fantasy_relevant]

    async def fetch_league_snapshot(self, league_id: str, *, weeks_back: int = 3) -> ImportedLeagueSnapshot:
        """Sleeper-optimised: fetch the raw league once and reuse it."""
        raw_league = await self.client.get_league(league_id)
        fallback_week = None
        if not (raw_league.get("settings") or {}).get("leg"):
            fallback_week = (await self.get_state()).week
        league = mappers.map_league_details(raw_league, fallback_week=fallback_week)

        raw_rosters = await self.client.get_rosters(league_id)
        raw_users = await self.client.get_league_users(league_id)
        teams = mappers.map_teams(raw_rosters, raw_users, (raw_league.get("settings") or {}).get("waiver_budget"))
        rosters = [mappers.map_roster(r, league.roster_positions) for r in raw_rosters]
        players = await self.get_players()

        weeks = [w for w in range(league.current_week - weeks_back, league.current_week + 1) if w >= 1]
        matchups: list[MatchupData] = []
        transactions: list[TransactionData] = []
        for week in weeks:
            matchups.extend(await self.get_matchups(league_id, week))
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
