from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import ContextService, CurrentUser, SessionDep, SettingsDep, StateDep
from app.core.errors import NotFoundError
from app.repositories import LeagueRepository
from app.schemas.league import LeagueOut, PlayerOut
from app.services.demo_service import DemoService

router = APIRouter(tags=["misc"])


@router.get("/health")
async def health(settings: SettingsDep, state: StateDep) -> dict:
    return {
        "status": "ok",
        "environment": settings.environment,
        "ai_enabled": state.llm is not None,
        "ai_provider": getattr(state.llm, "provider", None) if state.llm is not None else None,
        "demo_enabled": settings.demo_enabled,
        "nfl_data_provider": state.nfl_data.name,
    }


@router.post("/demo/league", response_model=LeagueOut, status_code=status.HTTP_201_CREATED)
async def create_demo_league(
    user: CurrentUser, session: SessionDep, settings: SettingsDep, ctx: ContextService
) -> LeagueOut:
    league = await DemoService(session, ctx.nfl_data, enabled=settings.demo_enabled).create_demo_league(user.id)
    return await ctx.league_out(league)


@router.get("/players/{player_id}", response_model=PlayerOut)
async def get_player(
    player_id: UUID, user: CurrentUser, session: SessionDep, ctx: ContextService, league_id: UUID
) -> PlayerOut:
    league = await LeagueRepository(session).get_owned(user.id, league_id)
    if league is None:
        raise NotFoundError("League not found.")
    return await ctx.get_player_in_league(league, player_id, league.current_week)
