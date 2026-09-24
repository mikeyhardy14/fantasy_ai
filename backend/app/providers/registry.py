from app.core.config import Settings
from app.core.errors import ProviderNotImplemented
from app.domain.enums import Provider
from app.providers.base import FantasyProvider
from app.providers.sleeper import SleeperClient, SleeperProvider
from app.providers.stubs import ESPNProvider, NFLFantasyProvider, YahooProvider


class ProviderRegistry:
    """Resolves a Provider enum to a configured adapter instance.

    Built once per application (see app.api.deps) so HTTP clients and caches
    are shared. Tests can construct it with a custom Sleeper client whose
    transport is mocked.
    """

    def __init__(self, settings: Settings, *, sleeper_client: SleeperClient | None = None):
        client = sleeper_client or SleeperClient(
            base_url=settings.sleeper_base_url,
            timeout=settings.sleeper_timeout_seconds,
            player_cache_path=settings.sleeper_player_cache_path,
            player_cache_ttl_seconds=settings.sleeper_player_cache_ttl_hours * 3600,
        )
        self._providers: dict[Provider, FantasyProvider] = {
            Provider.SLEEPER: SleeperProvider(client),
            Provider.YAHOO: YahooProvider(),
            Provider.ESPN: ESPNProvider(),
            Provider.NFL: NFLFantasyProvider(),
        }

    def get(self, provider: Provider | str) -> FantasyProvider:
        key = Provider(provider)
        try:
            return self._providers[key]
        except KeyError as exc:
            raise ProviderNotImplemented(provider=key.value) from exc

    def register(self, provider: FantasyProvider) -> None:
        self._providers[provider.provider] = provider

    def describe(self) -> list[dict]:
        return [
            {
                "provider": p.provider.value,
                "capabilities": p.capabilities.model_dump(),
                "implemented": p.provider == Provider.SLEEPER,
            }
            for p in self._providers.values()
        ]
