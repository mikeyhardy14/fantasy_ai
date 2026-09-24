from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import (
    AI,
    CipherDep,
    ContextService,
    CurrentUser,
    OwnedLeague,
    Providers,
    SessionDep,
    SettingsDep,
    ToolCtx,
)
from app.core.errors import ProviderNotImplemented
from app.domain.enums import Provider
from app.intelligence.recommendations import generate_recommendations
from app.schemas.ai import RecommendationOut, WeeklyBriefing
from app.schemas.league import (
    LeagueDetailOut,
    LeagueOut,
    LineupUpdateRequest,
    LineupUpdateResponse,
    RosterMoveRequest,
    MatchupOut,
    PlayerOut,
    PlayerSheetOut,
    RankingsOut,
    RosterNeedsOut,
    StandingsRowOut,
    SyncResponse,
    TeamOut,
    TransactionOut,
)
from app.services.sleeper_writes import build_sleeper_write_service
from app.services.sync_service import SyncService

router = APIRouter(prefix="/leagues", tags=["leagues"])

POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF", "DL", "LB", "DB"}


@router.get("", response_model=list[LeagueOut])
async def list_leagues(user: CurrentUser, session: SessionDep, ctx: ContextService) -> list[LeagueOut]:
    from app.repositories import LeagueRepository

    leagues = await LeagueRepository(session).list_for_user(user.id)
    return [await ctx.league_out(lg) for lg in leagues]


@router.get("/{league_id}", response_model=LeagueDetailOut)
async def get_league(league: OwnedLeague, ctx: ContextService) -> LeagueDetailOut:
    return await ctx.league_detail_out(league)


@router.get("/{league_id}/team", response_model=TeamOut)
async def get_team(
    league: OwnedLeague, ctx: ContextService, week: int | None = Query(default=None, ge=1, le=18)
) -> TeamOut:
    return await ctx.user_team_out(league, week)


@router.post("/{league_id}/lineup", response_model=LineupUpdateResponse)
async def update_lineup(
    body: LineupUpdateRequest,
    league: OwnedLeague,
    session: SessionDep,
    providers: Providers,
    ctx: ContextService,
    cipher: CipherDep,
    settings: SettingsDep,
) -> LineupUpdateResponse:
    service = build_sleeper_write_service(session, ctx, providers, cipher, settings.sleeper_graphql_url)
    return await service.set_lineup(league, body)


@router.post("/{league_id}/lineup/move", response_model=LineupUpdateResponse)
async def move_player(
    body: RosterMoveRequest,
    league: OwnedLeague,
    session: SessionDep,
    providers: Providers,
    ctx: ContextService,
    cipher: CipherDep,
    settings: SettingsDep,
) -> LineupUpdateResponse:
    service = build_sleeper_write_service(session, ctx, providers, cipher, settings.sleeper_graphql_url)
    return await service.move_player(league, body)


@router.get("/{league_id}/matchup", response_model=MatchupOut | None)
async def get_matchup(
    league: OwnedLeague, ctx: ContextService, week: int | None = Query(default=None, ge=1, le=18)
) -> MatchupOut | None:
    team = await ctx.user_team(league)
    if team is None:
        return None
    return await ctx.matchup_out(league, team, week)


@router.get("/{league_id}/players/{player_id}", response_model=PlayerSheetOut)
async def get_player_sheet(
    player_id: UUID,
    league: OwnedLeague,
    ctx: ContextService,
    week: int | None = Query(default=None, ge=1, le=18),
) -> PlayerSheetOut:
    return await ctx.player_sheet(league, player_id, week)


@router.get("/{league_id}/rankings", response_model=RankingsOut)
async def get_rankings(
    league: OwnedLeague,
    ctx: ContextService,
    week: int | None = Query(default=None, ge=1, le=18),
    position: str | None = Query(default=None, max_length=5),
) -> RankingsOut:
    pos = position.upper() if position else None
    if pos and pos not in {"QB", "RB", "WR", "TE", "K", "DEF"}:
        pos = None
    return await ctx.rankings(league, week, pos)


@router.get("/{league_id}/players", response_model=list[PlayerOut])
async def get_players(
    league: OwnedLeague,
    ctx: ContextService,
    position: str | None = Query(default=None, max_length=5),
    search: str | None = Query(default=None, min_length=2, max_length=60),
    available: bool = Query(default=True, description="Only players not on any roster"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PlayerOut]:
    pos = position.upper() if position else None
    if pos and pos not in POSITIONS:
        pos = None
    if available:
        return await ctx.available_players(league, position=pos, search=search, limit=limit)
    return await ctx.search_players(league, search=search, position=pos, limit=limit)


@router.get("/{league_id}/standings", response_model=list[StandingsRowOut])
async def get_standings(league: OwnedLeague, ctx: ContextService) -> list[StandingsRowOut]:
    return await ctx.standings(league)


@router.get("/{league_id}/transactions", response_model=list[TransactionOut])
async def get_transactions(
    league: OwnedLeague, ctx: ContextService, limit: int = Query(default=25, ge=1, le=100)
) -> list[TransactionOut]:
    return await ctx.recent_transactions(league, limit)


@router.get("/{league_id}/needs", response_model=RosterNeedsOut)
async def get_needs(league: OwnedLeague, ctx: ContextService) -> RosterNeedsOut:
    team_view = await ctx.user_team_out(league)
    return ctx.roster_needs(league, team_view)


@router.get("/{league_id}/recommendations", response_model=list[RecommendationOut])
async def get_recommendations(
    league: OwnedLeague, ctx: ContextService, week: int | None = Query(default=None, ge=1, le=18)
) -> list[RecommendationOut]:
    team_ctx = await ctx.build_context(league, week)
    return [RecommendationOut.from_domain(r) for r in generate_recommendations(team_ctx)]


@router.get("/{league_id}/briefing", response_model=WeeklyBriefing)
async def get_briefing(tool_ctx: ToolCtx, ai: AI) -> WeeklyBriefing:
    return await ai.weekly_briefing(tool_ctx)


@router.post("/{league_id}/sync", response_model=SyncResponse)
async def sync_league(
    league: OwnedLeague, session: SessionDep, providers: Providers, ctx: ContextService
) -> SyncResponse:
    if league.provider == Provider.DEMO.value:
        from app.services.demo_service import DemoService

        await DemoService(session, ctx.nfl_data).create_demo_league(league.fantasy_account.user_id)
        return SyncResponse(league=await ctx.league_out(league), message="Demo league refreshed.")
    try:
        adapter = providers.get(league.provider)
    except ProviderNotImplemented:
        raise
    await SyncService(session).sync_league(league, adapter)
    return SyncResponse(league=await ctx.league_out(league), message="League synced.")
