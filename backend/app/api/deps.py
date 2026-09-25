"""FastAPI dependency wiring (composition root)."""

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import LLMClient, build_llm
from app.ai.service import AIService
from app.ai.tools import ToolContext, build_tool_context
from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, UnauthorizedError
from app.core.security import CredentialCipher, decode_access_token, resolve_credentials_key
from app.db.session import Database
from app.models import League, User
from app.nfl_data import LocalFileNFLDataProvider, NFLDataProvider
from app.nfl_data.espn import ESPNScheduleClient
from app.nfl_data.live import LiveNFLDataProvider
from app.nfl_data.props import EspnPropClient
from app.nfl_data.sleeper_stats import SleeperProjections, SleeperWeeklyStats
from app.providers import ProviderRegistry
from app.repositories import LeagueRepository, UserRepository
from app.services.league_context import LeagueContextService
from app.services.sleeper_writes import build_sleeper_write_service

bearer = HTTPBearer(auto_error=False)


class AppState:
    """Long-lived singletons created once at startup."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = Database(settings)
        self.cipher = CredentialCipher(resolve_credentials_key(settings))
        self.providers = ProviderRegistry(settings)
        local_nfl = LocalFileNFLDataProvider(settings.nfl_data_file)
        # Tests stay on the file so a suite never calls ESPN.
        if settings.environment == "test":
            self.nfl_data: NFLDataProvider = local_nfl
        else:
            self.nfl_data = LiveNFLDataProvider(
                local_nfl,
                ESPNScheduleClient(
                    settings.espn_schedule_cache_dir,
                    ttl_seconds=settings.espn_schedule_ttl_hours * 3600,
                ),
            )
        self.weekly_stats: SleeperWeeklyStats | None = None
        self.props: EspnPropClient | None = None
        self.sleeper_projections: SleeperProjections | None = None
        if settings.environment != "test":
            self.weekly_stats = SleeperWeeklyStats(settings.espn_schedule_cache_dir, settings.sleeper_base_url)
            self.props = EspnPropClient(settings.espn_schedule_cache_dir, settings.sleeper_player_cache_path)
            self.sleeper_projections = SleeperProjections(settings.espn_schedule_cache_dir, settings.sleeper_base_url)
        self.llm: LLMClient | None = build_llm(settings)


def get_state(request: Request) -> AppState:
    return request.app.state.container


def get_app_settings(state: Annotated[AppState, Depends(get_state)]) -> Settings:
    return state.settings


async def get_session(state: Annotated[AppState, Depends(get_state)]) -> AsyncIterator[AsyncSession]:
    async for session in state.db.session():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
StateDep = Annotated[AppState, Depends(get_state)]


async def get_current_user(
    session: SessionDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Authentication required.")
    user_id = decode_access_token(credentials.credentials, settings)
    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("User no longer exists.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_owned_league(league_id: UUID, session: SessionDep, user: CurrentUser) -> League:
    """Authorization boundary for every /leagues/{league_id} route."""
    league = await LeagueRepository(session).get_owned(user.id, league_id)
    if league is None:
        raise NotFoundError("League not found.")
    return league


OwnedLeague = Annotated[League, Depends(get_owned_league)]


def get_providers(state: StateDep) -> ProviderRegistry:
    return state.providers


def get_cipher(state: StateDep) -> CredentialCipher:
    return state.cipher


def get_nfl_data(state: StateDep) -> NFLDataProvider:
    return state.nfl_data


def get_context_service(session: SessionDep, state: StateDep) -> LeagueContextService:
    return LeagueContextService(
        session, state.nfl_data, state.weekly_stats, state.props, state.sleeper_projections
    )


ContextService = Annotated[LeagueContextService, Depends(get_context_service)]
Providers = Annotated[ProviderRegistry, Depends(get_providers)]
CipherDep = Annotated[CredentialCipher, Depends(get_cipher)]


def get_ai_service(state: StateDep) -> AIService:
    return AIService(state.llm, max_tool_rounds=state.settings.ai_max_tool_rounds)


AI = Annotated[AIService, Depends(get_ai_service)]


async def get_tool_context(
    league: OwnedLeague,
    user: CurrentUser,
    session: SessionDep,
    service: ContextService,
    state: StateDep,
    providers: Providers,
    cipher: CipherDep,
    week: int | None = None,
) -> ToolContext:
    writes = build_sleeper_write_service(session, service, providers, cipher, state.settings.sleeper_graphql_url)
    return await build_tool_context(session, user.id, league.id, service, week, writes)


ToolCtx = Annotated[ToolContext, Depends(get_tool_context)]
