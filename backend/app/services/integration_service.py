"""Connecting fantasy accounts and importing leagues (provider-agnostic)."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ProviderNotFound, ValidationFailed
from app.core.logging import get_logger
from app.domain.enums import Provider, SyncStatus
from app.domain.provider_models import LeagueSummary
from app.models import FantasyAccount, League
from app.providers.registry import ProviderRegistry
from app.repositories import FantasyAccountRepository, LeagueRepository
from app.services.sync_service import SyncService

log = get_logger(__name__)


class IntegrationService:
    def __init__(self, session: AsyncSession, providers: ProviderRegistry):
        self.session = session
        self.providers = providers
        self.accounts = FantasyAccountRepository(session)
        self.leagues = LeagueRepository(session)

    async def connect(self, user_id: UUID, provider: Provider, identifier: str) -> FantasyAccount:
        identifier = identifier.strip()
        if not identifier:
            raise ValidationFailed("Please enter a username.")
        adapter = self.providers.get(provider)
        try:
            identity = await adapter.get_user(identifier)
        except ProviderNotFound as exc:
            raise ProviderNotFound(
                f"No {provider.value.title()} user named '{identifier}' was found.",
                provider=provider.value,
            ) from exc
        account = await self.accounts.upsert(user_id, provider.value, identity)
        await self.session.commit()
        log.info("integration.connected", user_id=str(user_id), provider=provider.value)
        return account

    async def list_accounts(self, user_id: UUID) -> list[FantasyAccount]:
        return await self.accounts.list_for_user(user_id)

    async def _account_for(self, user_id: UUID, provider: Provider, account_id: UUID | None) -> FantasyAccount:
        if account_id is not None:
            account = await self.accounts.get_for_user(user_id, account_id)
            if account is None or account.provider != provider.value:
                raise NotFoundError("Connected account not found.")
            return account
        accounts = await self.accounts.get_by_provider(user_id, provider.value)
        if not accounts:
            raise NotFoundError(f"No {provider.value.title()} account is connected yet.")
        return accounts[-1]

    async def list_provider_leagues(
        self, user_id: UUID, provider: Provider, season: int | None, account_id: UUID | None = None
    ) -> tuple[FantasyAccount, int, list[LeagueSummary], set[str]]:
        account = await self._account_for(user_id, provider, account_id)
        adapter = self.providers.get(provider)
        if season is None:
            season = (await adapter.get_state()).season
        summaries = await adapter.get_leagues(account.external_user_id, season)
        imported = {
            lg.external_league_id
            for lg in await self.leagues.list_for_user(user_id)
            if lg.fantasy_account_id == account.id
        }
        return account, season, summaries, imported

    async def import_league(
        self, user_id: UUID, provider: Provider, external_league_id: str, account_id: UUID | None = None
    ) -> League:
        account = await self._account_for(user_id, provider, account_id)
        adapter = self.providers.get(provider)

        league = await self.leagues.get_by_identity(account.id, external_league_id)
        if league is None:
            details = await adapter.get_league(external_league_id)
            league = League(
                fantasy_account_id=account.id,
                provider=provider.value,
                external_league_id=external_league_id,
                name=details.name,
                season=details.season,
                team_count=details.team_count,
                current_week=details.current_week,
                scoring_settings=details.scoring_settings,
                roster_settings=details.roster_settings,
                league_settings=details.league_settings,
                sync_status=SyncStatus.IDLE,
            )
            self.leagues.add(league)
            await self.session.flush()
            league.fantasy_account = account

        await SyncService(self.session).sync_league(league, adapter)
        return league
