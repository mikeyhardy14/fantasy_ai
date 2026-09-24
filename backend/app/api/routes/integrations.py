from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CipherDep, ContextService, CurrentUser, Providers, SessionDep, SettingsDep
from app.domain.enums import Provider
from app.schemas.league import (
    ConnectRequest,
    FantasyAccountOut,
    LeagueOut,
    ProviderLeagueOut,
    ProviderLeaguesResponse,
    SleeperTokenRequest,
    fantasy_account_out,
)
from app.services.integration_service import IntegrationService
from app.services.sleeper_writes import build_sleeper_write_service

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/accounts", response_model=list[FantasyAccountOut])
async def list_accounts(user: CurrentUser, session: SessionDep, providers: Providers) -> list[FantasyAccountOut]:
    accounts = await IntegrationService(session, providers).list_accounts(user.id)
    return [fantasy_account_out(a) for a in accounts]


@router.get("/providers")
async def list_providers(providers: Providers) -> list[dict]:
    return providers.describe()


@router.post("/sleeper/connect", response_model=FantasyAccountOut, status_code=status.HTTP_201_CREATED)
async def connect_sleeper(
    body: ConnectRequest, user: CurrentUser, session: SessionDep, providers: Providers
) -> FantasyAccountOut:
    account = await IntegrationService(session, providers).connect(user.id, Provider.SLEEPER, body.username)
    return fantasy_account_out(account)


@router.get("/sleeper/leagues", response_model=ProviderLeaguesResponse)
async def list_sleeper_leagues(
    user: CurrentUser,
    session: SessionDep,
    providers: Providers,
    season: int | None = Query(default=None, ge=2015, le=2100),
    account_id: UUID | None = None,
) -> ProviderLeaguesResponse:
    account, resolved_season, leagues, imported = await IntegrationService(
        session, providers
    ).list_provider_leagues(user.id, Provider.SLEEPER, season, account_id)
    return ProviderLeaguesResponse(
        account=fantasy_account_out(account),
        season=resolved_season,
        leagues=[
            ProviderLeagueOut(**lg.model_dump(), imported=lg.external_league_id in imported) for lg in leagues
        ],
    )


@router.post("/sleeper/leagues/{external_league_id}/import", response_model=LeagueOut)
async def import_sleeper_league(
    external_league_id: str,
    user: CurrentUser,
    session: SessionDep,
    providers: Providers,
    ctx: ContextService,
    account_id: UUID | None = None,
) -> LeagueOut:
    league = await IntegrationService(session, providers).import_league(
        user.id, Provider.SLEEPER, external_league_id, account_id
    )
    return await ctx.league_out(league)


@router.put("/sleeper/token", response_model=FantasyAccountOut)
async def save_sleeper_token(
    body: SleeperTokenRequest,
    user: CurrentUser,
    session: SessionDep,
    providers: Providers,
    ctx: ContextService,
    cipher: CipherDep,
    settings: SettingsDep,
    account_id: UUID | None = None,
) -> FantasyAccountOut:
    account = await build_sleeper_write_service(
        session, ctx, providers, cipher, settings.sleeper_graphql_url
    ).save_token(user.id, body.token, account_id)
    return fantasy_account_out(account)


@router.delete("/sleeper/token", response_model=FantasyAccountOut)
async def clear_sleeper_token(
    user: CurrentUser,
    session: SessionDep,
    providers: Providers,
    ctx: ContextService,
    cipher: CipherDep,
    settings: SettingsDep,
    account_id: UUID | None = None,
) -> FantasyAccountOut:
    account = await build_sleeper_write_service(
        session, ctx, providers, cipher, settings.sleeper_graphql_url
    ).clear_token(user.id, account_id)
    return fantasy_account_out(account)
