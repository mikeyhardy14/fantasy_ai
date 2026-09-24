"""Providers that are designed but not yet implemented.

They declare their capabilities (so the UI can show the right connect flow)
and raise ProviderNotImplemented for every data call. When implementing one:

1. Add a `<name>/client.py` handling auth (OAuth for Yahoo, cookie/OAuth for
   ESPN/NFL) using FantasyAccount.encrypted_credentials via CredentialCipher.
2. Add `<name>/mappers.py` converting payloads to app.domain.provider_models.
3. Replace the stub class with a real implementation and register it in
   app.providers.registry.
"""

from app.core.errors import ProviderNotImplemented
from app.domain.enums import Provider
from app.domain.provider_models import (
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


class _NotImplementedProvider(FantasyProvider):
    def _fail(self) -> ProviderNotImplemented:
        return ProviderNotImplemented(
            f"{self.provider.value.title()} integration is not available yet.",
            provider=self.provider.value,
        )

    async def get_state(self) -> ProviderState:
        raise self._fail()

    async def get_user(self, identifier: str) -> ProviderUser:
        raise self._fail()

    async def get_leagues(self, external_user_id: str, season: int) -> list[LeagueSummary]:
        raise self._fail()

    async def get_league(self, league_id: str) -> LeagueDetails:
        raise self._fail()

    async def get_teams(self, league_id: str) -> list[TeamData]:
        raise self._fail()

    async def get_rosters(self, league_id: str) -> list[RosterData]:
        raise self._fail()

    async def get_matchups(self, league_id: str, week: int) -> list[MatchupData]:
        raise self._fail()

    async def get_transactions(self, league_id: str, week: int) -> list[TransactionData]:
        raise self._fail()

    async def get_players(self) -> dict[str, PlayerData]:
        raise self._fail()

    async def get_available_players(self, league_id: str) -> list[PlayerData]:
        raise self._fail()


class YahooProvider(_NotImplementedProvider):
    provider = Provider.YAHOO
    capabilities = ProviderCapabilities(
        auth_type="oauth", supports_projections=True, supports_faab=True
    )


class ESPNProvider(_NotImplementedProvider):
    provider = Provider.ESPN
    capabilities = ProviderCapabilities(
        auth_type="cookie", supports_projections=True, supports_faab=True
    )


class NFLFantasyProvider(_NotImplementedProvider):
    provider = Provider.NFL
    capabilities = ProviderCapabilities(
        auth_type="oauth", supports_projections=True, supports_faab=True
    )
