"""Builds enriched, provider-neutral views of a league for the API and AI tools.

Combines the normalized DB (fantasy platform data) with the NFLDataProvider
(bye weeks, projections, stats). Everything the intelligence layer consumes is
produced here.
"""

import asyncio
import random
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.trade_review import pick_lines
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.domain.enums import NON_LINEUP_SLOTS
from app.intelligence.context import TeamContext
from app.intelligence.lineup import lineup_issues, player_flags
from app.intelligence.roster_needs import compute_roster_needs
from app.models import FantasyTeam, League, Player, RosterEntry, Transaction
from app.nfl_data import NFLDataProvider, PlayerProjection, player_key
from app.nfl_data.headshot import headshot_url
from app.nfl_data.live import depth_for_player
from app.nfl_data.props import EspnPropClient, prop_components
from app.nfl_data.rankings import RankCandidate, build_rankings, ruled_out
from app.nfl_data.sleeper_stats import (
    SleeperProjections,
    SleeperWeeklyStats,
    projection_points,
    score_stats,
    summarize_stats,
)
from app.nfl_data.usage import UsageTable, build_usage
from app.nfl_data.vegas import explain_projection, normalize_position
from app.nfl_data.vegas_ff import project_player, scoring_from_league, sims_for, start_sit
from app.repositories import (
    MatchupRepository,
    PlayerRepository,
    RosterRepository,
    TeamRepository,
    TransactionRepository,
)
from app.schemas.league import (
    LeagueDetailOut,
    LeagueOut,
    MatchupOut,
    MatchupSideOut,
    NflGameOut,
    PlayerOut,
    PlayerSheetOut,
    PropLineOut,
    RankingRowOut,
    RankingsOut,
    RosterNeedsOut,
    RosterSlotOut,
    SlotCallOut,
    StandingsRowOut,
    TeamOut,
    TeamSummaryOut,
    TransactionOut,
    fantasy_account_out,
)

log = get_logger(__name__)


class LeagueContextService:
    def __init__(
        self,
        session: AsyncSession,
        nfl_data: NFLDataProvider,
        weekly_stats: SleeperWeeklyStats | None = None,
        props: EspnPropClient | None = None,
        sleeper_projections: SleeperProjections | None = None,
    ):
        self.session = session
        self.nfl_data = nfl_data
        self.weekly_stats = weekly_stats
        self.props = props
        self.sleeper_projections = sleeper_projections
        self.teams = TeamRepository(session)
        self.players = PlayerRepository(session)
        self.rosters = RosterRepository(session)
        self.matchups = MatchupRepository(session)
        self.transactions = TransactionRepository(session)
        self._usage_cache: dict[tuple[int, int], UsageTable] = {}

    # ---- league ---------------------------------------------------------------

    async def user_team(self, league: League) -> FantasyTeam | None:
        owner = league.fantasy_account.external_user_id
        return await self.teams.get_by_owner(league.id, owner)

    async def league_out(self, league: League) -> LeagueOut:
        team = await self.user_team(league)
        return LeagueOut(
            id=league.id,
            provider=league.provider,
            external_league_id=league.external_league_id,
            name=league.name,
            season=league.season,
            team_count=league.team_count,
            current_week=league.current_week,
            status=league.status,
            avatar=league.avatar,
            scoring_type=league.league_settings.get("scoring_type"),
            last_synced_at=league.last_synced_at,
            sync_status=league.sync_status,
            sync_error=league.sync_error,
            user_team_id=team.id if team else None,
            user_team_name=team.name if team else None,
        )

    async def league_detail_out(self, league: League) -> LeagueDetailOut:
        base = await self.league_out(league)
        return LeagueDetailOut(
            **base.model_dump(),
            scoring_settings=league.scoring_settings,
            roster_settings=league.roster_settings,
            league_settings=league.league_settings,
            account=fantasy_account_out(league.fantasy_account),
        )

    # ---- players -------------------------------------------------------------

    async def _week_projection(self, player: Player, league: League, week: int, on_bye: bool):
        """Saved number, then the Vegas share model, then props, then Sleeper's published total."""
        key = player_key(player.name, player.position, player.nfl_team)
        projection = await self.nfl_data.get_projection(key, league.season, week)
        if projection is not None or on_bye:
            return projection
        modeled = await self._modeled_projection(player, league, week)
        if modeled is not None:
            return modeled
        if self.props is not None:
            projection = await self.props.project_named(
                player.name,
                player.position,
                league.season,
                week,
                league.scoring_settings or {},
            )
            if projection is not None:
                return projection
        if normalize_position(player.position) == "DEF" and player.nfl_team:
            from_line = await self.nfl_data.project_from_line(
                nfl_team=player.nfl_team,
                position=player.position,
                depth=depth_for_player(player.extra),
                season=league.season,
                week=week,
                scoring=league.scoring_settings or {},
            )
            if from_line is not None:
                return from_line
        return await self._sleeper_projection(player, league, week)

    async def _sleeper_projection(self, player: Player, league: League, week: int) -> PlayerProjection | None:
        if self.sleeper_projections is None:
            return None
        sleeper_id = player.external_id_for(league.provider)
        if not sleeper_id:
            return None
        stats = await self.sleeper_projections.player(league.season, week, sleeper_id)
        points, label = projection_points(stats, league.scoring_settings)
        if points is None:
            return None
        return PlayerProjection(
            week=week,
            points=points,
            source="sleeper",
            note=f"{label} projection for this week.",
        )

    async def _usage_table(self, league: League, week: int) -> UsageTable:
        key = (league.season, week)
        cached = self._usage_cache.get(key)
        if cached is not None:
            return cached
        stats = self.weekly_stats
        if stats is None or week <= 1:
            return UsageTable()
        blobs = await asyncio.gather(*(stats.week(league.season, past) for past in range(1, week)))
        roster = await self.players.list_active(league.provider, ("QB", "RB", "WR", "TE"))
        teams: dict[str, str] = {}
        injuries: dict[str, str | None] = {}
        positions: dict[str, str | None] = {}
        for person in roster:
            sleeper_id = person.external_id_for(league.provider)
            if not sleeper_id or not person.nfl_team:
                continue
            teams[sleeper_id] = person.nfl_team
            injuries[sleeper_id] = person.injury_status
            positions[sleeper_id] = person.position
        table = build_usage(list(zip(range(1, week), blobs, strict=True)), teams, injuries, positions)
        self._usage_cache[key] = table
        return table

    async def _modeled_projection(self, player: Player, league: League, week: int):
        """Share of the Vegas team total from this season's earlier games. None without that history."""
        if self.weekly_stats is None or week <= 1 or not player.nfl_team:
            return None
        position = normalize_position(player.position)
        if position not in {"QB", "RB", "WR", "TE"}:
            return None
        sleeper_id = player.external_id_for(league.provider)
        if not sleeper_id:
            return None
        schedule = await self.nfl_data.get_schedule(player.nfl_team, league.season)
        game = next((item for item in schedule if item.week == week and item.opponent), None)
        if game is None or game.total is None or game.spread is None:
            return None
        implied = game.implied_points if game.implied_points is not None else (game.total - game.spread) / 2
        table = await self._usage_table(league, week)
        games = table.games.get(sleeper_id) or []
        if not games:
            return None
        status = (player.injury_status or "").strip().lower()
        return project_player(
            position=position,
            week=week,
            implied=implied,
            margin=-game.spread,
            team_history=table.team_history.get(player.nfl_team) or {},
            player_games=games,
            scoring=scoring_from_league(league.scoring_settings or {}),
            teammates_out_share=table.out_share(player.nfl_team, sleeper_id),
            questionable=status in {"questionable", "q"},
        )

    async def player_out(self, player: Player, league: League, week: int) -> PlayerOut:
        key = player_key(player.name, player.position, player.nfl_team)
        bye = await self.nfl_data.get_bye_week(player.nfl_team, league.season) if player.nfl_team else None
        opponent = await self.nfl_data.get_opponent(player.nfl_team, league.season, week) if player.nfl_team else None
        on_bye = bye == week if bye is not None else False
        if on_bye:
            opponent = None
        projection = await self._week_projection(player, league, week, on_bye)
        stats = await self.nfl_data.get_season_stats(key, league.season)
        season_points = stats.fantasy_points if stats else None
        per_game = stats.fantasy_points_per_game if stats else None
        if season_points is None:
            scored, games = await self._points_scored(player, league, await self._season_week_blobs(league, week))
            if scored is not None:
                season_points = scored
                if per_game is None and games:
                    per_game = round(scored / games, 1)
        schedule = await self.nfl_data.get_schedule(player.nfl_team, league.season) if player.nfl_team else []
        live_game = getattr(self.nfl_data, "live_schedule_game", None)
        if player.nfl_team and live_game is not None:
            fresh = await live_game(player.nfl_team, league.season, week)
            if fresh is not None:
                schedule = [fresh if item.week == week else item for item in schedule]
                if not any(item.week == week for item in schedule):
                    schedule = [*schedule, fresh]
        return PlayerOut(
            id=player.id,
            name=player.name,
            position=player.position,
            fantasy_positions=player.fantasy_positions or ([player.position] if player.position else []),
            nfl_team=player.nfl_team,
            status=player.status,
            injury_status=player.injury_status,
            injury_body_part=player.injury_body_part,
            age=player.age,
            years_exp=player.years_exp,
            bye_week=bye,
            on_bye=on_bye,
            opponent=opponent,
            projected_points=projection.points if projection else None,
            projection_note=projection.note if projection else None,
            projection_detail=_sim_detail(projection),
            projection_reasons=explain_projection(
                projection,
                on_bye=on_bye,
                opponent=opponent,
                team=player.nfl_team,
                position=player.position,
            ),
            projection_lines=[
                PropLineOut(**row) for row in prop_components(projection.detail if projection else None)
            ],
            season_points=season_points,
            points_per_game=per_game,
            headshot_url=headshot_url(player),
            schedule=schedule,
            external_ids={e.provider: e.external_id for e in player.external_ids},
        )

    async def player_sheet(self, league: League, player_id: UUID, week: int | None = None) -> PlayerSheetOut:
        week = week or league.current_week
        player = await self.get_player_in_league(league, player_id, week)
        sleeper_id = player.external_ids.get("sleeper")
        if not sleeper_id:
            return PlayerSheetOut(
                player=player,
                games_note="Recent games come from Sleeper's weekly stat lines, and this player has no Sleeper id.",
            )
        if self.weekly_stats is None:
            return PlayerSheetOut(player=player, games_note="Recent game stats are not loaded in this environment.")
        opponents = {game.week: (game.opponent, game.home) for game in player.schedule}
        try:
            games = await self.weekly_stats.recent(
                sleeper_id,
                league.season,
                week,
                scoring=league.scoring_settings or {},
                opponents=opponents,
            )
        except Exception as exc:
            log.warning("player.recent_games_failed", error=str(exc))
            return PlayerSheetOut(player=player, games_note="Recent stats could not be loaded.")
        note = None if games else "No stat lines yet for the weeks already played."
        return PlayerSheetOut(player=player, recent_games=games, games_note=note)

    async def get_player_in_league(self, league: League, player_id: UUID, week: int) -> PlayerOut:
        player = await self.players.get(player_id)
        if player is None or player.external_id_for(league.provider) is None:
            raise NotFoundError("Player not found in this league's player pool.")
        return await self.player_out(player, league, week)

    async def available_players(
        self,
        league: League,
        *,
        position: str | None = None,
        search: str | None = None,
        limit: int = 50,
        week: int | None = None,
    ) -> list[PlayerOut]:
        week = week or league.current_week
        rostered = await self.players.rostered_player_ids(league.id, week)
        # A name search is a small match list. Browsing, including one position,
        # has to rank by this week's projection before the response is cut off.
        query = (search or "").strip() or None
        fetch_limit = limit if query else max(limit, 2000)
        players = await self.players.search(
            provider=league.provider,
            exclude_ids=rostered,
            position=position,
            query=query,
            limit=fetch_limit,
        )
        if query is None:
            ranked: list[tuple[float | None, Player]] = []
            for player in players:
                bye = await self.nfl_data.get_bye_week(player.nfl_team, league.season) if player.nfl_team else None
                on_bye = bye == week if bye is not None else False
                projection = await self._week_projection(player, league, week, on_bye)
                ranked.append((None if projection is None else projection.points, player))
            ranked.sort(key=lambda row: (row[0] is None, -(row[0] or 0), row[1].name))
            players = [player for _, player in ranked[:limit]]
        out = [await self.player_out(p, league, week) for p in players]
        out.sort(
            key=lambda p: (
                p.projected_points is None,
                -(p.projected_points or 0),
                p.points_per_game is None,
                -(p.points_per_game or 0),
                p.name,
            )
        )
        return out

    async def _season_week_blobs(self, league: League, week: int) -> list[dict]:
        if self.weekly_stats is None or week < 1:
            return []
        return list(await asyncio.gather(*(self.weekly_stats.week(league.season, item) for item in range(1, week + 1))))

    async def _points_scored(self, player: Player, league: League, blobs: list[dict]) -> tuple[float | None, int | None]:
        """Season fantasy points already scored, then games with a stat line."""
        key = player.external_id_for(league.provider) or str(player.id)
        stats = await self.nfl_data.get_season_stats(key, league.season)
        if stats is not None and stats.fantasy_points is not None:
            return float(stats.fantasy_points), stats.games_played
        sleeper_id = player.external_id_for(league.provider)
        if not sleeper_id or not blobs:
            return None, None
        total = 0.0
        games = 0
        scoring = league.scoring_settings or {}
        for blob in blobs:
            raw = blob.get(sleeper_id)
            if not isinstance(raw, dict):
                continue
            points, _label = score_stats(raw, scoring)
            if points is None:
                continue
            total += points
            games += 1
        if games == 0:
            return None, None
        return round(total, 1), games

    async def search_players(
        self, league: League, *, search: str | None, position: str | None, limit: int, week: int | None = None
    ) -> list[PlayerOut]:
        week = week or league.current_week
        # Name search stays a small match list. Browsing "all players" has to
        # rank the pool by points scored before the response limit.
        pool = limit if search else max(limit, 2000)
        players = await self.players.search(
            provider=league.provider, position=position, query=search, limit=pool
        )
        blobs = [] if search else await self._season_week_blobs(league, week)
        scored: list[tuple[float | None, int | None, Player]] = [
            (*await self._points_scored(player, league, blobs), player) for player in players
        ]
        scored.sort(key=lambda item: (item[0] is None, -(item[0] or 0), item[2].name))
        out: list[PlayerOut] = []
        for points, games, player in scored[:limit]:
            row = await self.player_out(player, league, week)
            updates: dict = {}
            if row.season_points is None and points is not None:
                updates["season_points"] = points
            if row.points_per_game is None and points is not None and games:
                updates["points_per_game"] = round(points / games, 1)
            if updates:
                row = row.model_copy(update=updates)
            out.append(row)
        out.sort(key=lambda row: (row.season_points is None, -(row.season_points or 0), row.name))
        return out

    async def _ranking_scope(
        self, league: League, week: int, scope: str | None
    ) -> tuple[set[str] | None, set[str] | None]:
        if scope == "mine":
            team = await self.user_team(league)
            entries = await self.rosters.list_for_team(team.id, week) if team else []
            return {str(entry.player_id) for entry in entries}, None
        if scope == "available":
            entries = await self.rosters.list_for_league(league.id, week)
            return None, {str(entry.player_id) for entry in entries}
        return None, None

    async def rankings(
        self,
        league: League,
        week: int | None = None,
        position: str | None = None,
        query: str | None = None,
        nfl_team: str | None = None,
        scope: str | None = None,
    ) -> RankingsOut:
        week = week or league.current_week
        raw = await self.players.list_active(league.provider, ("QB", "RB", "WR", "TE", "K", "DEF"))
        scored_weeks = await self._season_week_blobs(league, week)
        schedules: dict[str, list] = {}
        byes: dict[str, int | None] = {}
        candidates: list[RankCandidate] = []
        for player in raw:
            pos = normalize_position(player.position)
            if pos not in {"QB", "RB", "WR", "TE", "K", "DEF"}:
                continue
            team = player.nfl_team
            if not team:
                continue
            if team not in byes:
                byes[team] = await self.nfl_data.get_bye_week(team, league.season)
            if team not in schedules:
                schedules[team] = await self.nfl_data.get_schedule(team, league.season)
            on_bye = byes[team] == week
            game = next((item for item in schedules[team] if item.week == week), None)
            projection = await self._week_projection(player, league, week, on_bye)
            scored, _games = await self._points_scored(player, league, scored_weeks)
            candidates.append(
                RankCandidate(
                    player_id=str(player.id),
                    name=player.name,
                    position=pos,
                    nfl_team=team,
                    opponent=None if on_bye or game is None else game.opponent,
                    home=None if on_bye or game is None else game.home,
                    headshot_url=headshot_url(player),
                    injury_status=player.injury_status,
                    on_bye=on_bye,
                    ruled_out=ruled_out(player.injury_status),
                    total=None if on_bye or game is None else game.total,
                    spread=None if on_bye or game is None else game.spread,
                    implied_points=None if on_bye or game is None else game.implied_points,
                    win_probability=None if on_bye or game is None else game.win_probability,
                    book_count=0 if on_bye or game is None else game.book_count,
                    books=[] if on_bye or game is None else list(game.books),
                    projected_points=None if projection is None else projection.points,
                    projection_source=None if projection is None else projection.source,
                    season_points=scored,
                )
            )
        rostered = await self.rosters.list_for_league(league.id, week)
        user = await self.user_team(league)
        yours = {str(entry.player_id) for entry in rostered if user and entry.fantasy_team_id == user.id}
        taken = {str(entry.player_id) for entry in rostered} - yours
        only_ids, exclude_ids = await self._ranking_scope(league, week, scope)
        rows, truncated = build_rankings(
            candidates,
            team_count=league.team_count,
            roster_positions=list(league.roster_positions),
            position=position,
            query=query,
            nfl_team=nfl_team,
            only_ids=only_ids,
            exclude_ids=exclude_ids,
        )
        return RankingsOut(
            week=week,
            notes=[],
            truncated=truncated,
            rows=[
                RankingRowOut(
                    rank=row.rank,
                    player_id=UUID(row.player.player_id),
                    owned="you" if row.player.player_id in yours else "league" if row.player.player_id in taken else None,
                    name=row.player.name,
                    position=row.player.position,
                    nfl_team=row.player.nfl_team,
                    opponent=row.player.opponent,
                    home=row.player.home,
                    headshot_url=row.player.headshot_url,
                    injury_status=row.player.injury_status,
                    total=row.player.total,
                    spread=row.player.spread,
                    implied_points=row.player.implied_points,
                    win_probability=row.player.win_probability,
                    book_count=row.player.book_count,
                    books=row.player.books,
                    projected_points=row.player.projected_points,
                    projection_source=row.player.projection_source,
                    season_points=row.player.season_points,
                    vorp=row.vorp,
                )
                for row in rows
            ],
        )

    # ---- teams ----------------------------------------------------------------

    def team_summary(self, team: FantasyTeam, league: League) -> TeamSummaryOut:
        return TeamSummaryOut(
            id=team.id,
            name=team.name,
            owner_name=team.owner_name,
            avatar=team.avatar,
            wins=team.wins,
            losses=team.losses,
            ties=team.ties,
            record=team.record,
            points_for=team.points_for,
            points_against=team.points_against,
            faab_remaining=team.faab_remaining,
            waiver_position=team.waiver_position,
            is_user_team=team.owner_external_id == league.fantasy_account.external_user_id,
        )

    async def _slot_out(
        self, entry: RosterEntry, league: League, week: int, points: dict[str, float] | None
    ) -> RosterSlotOut:
        player = await self.player_out(entry.player, league, week)
        return RosterSlotOut(
            slot=entry.roster_slot,
            slot_index=entry.slot_index,
            is_starter=entry.is_starter,
            player=player,
            points=(points or {}).get(str(player.id)),
            flags=player_flags(player, week),
        )

    async def team_out(self, league: League, team: FantasyTeam, week: int | None = None) -> TeamOut:
        week = week or league.current_week
        entries = await self.rosters.list_for_team(team.id, week)
        if not entries and week != league.current_week:
            entries = await self.rosters.list_for_team(team.id, league.current_week)
        matchup = await self.matchups.get_for_team(league.id, week, team.id)
        points = matchup.player_points if matchup else {}
        slots = [await self._slot_out(e, league, week, points) for e in entries]
        starters = sorted([s for s in slots if s.is_starter], key=lambda s: (s.slot_index is None, s.slot_index or 0))
        bench = [s for s in slots if not s.is_starter and s.slot == "BN"]
        reserve = [s for s in slots if not s.is_starter and s.slot in ("IR", "TAXI")]
        lineup_slots = [p for p in league.roster_positions if p not in NON_LINEUP_SLOTS]

        projections = [s.player.projected_points for s in starters if s.player]
        known = [p for p in projections if p is not None]
        if not projections or not known:
            coverage, projected = "none", None
        elif len(known) == len(projections):
            coverage, projected = "full", round(sum(known), 1)
        else:
            coverage, projected = "partial", round(sum(known), 1)

        return TeamOut(
            team=self.team_summary(team, league),
            week=week,
            starters=starters,
            bench=bench,
            reserve=reserve,
            lineup_slots=lineup_slots,
            lineup_issues=lineup_issues(starters, lineup_slots),
            projected_points=projected,
            projection_coverage=coverage,
        )

    async def user_team_out(self, league: League, week: int | None = None) -> TeamOut:
        team = await self.user_team(league)
        if team is None:
            raise NotFoundError(
                "We could not find your team in this league. Make sure the connected account owns a roster here."
            )
        return await self.team_out(league, team, week)

    async def team_by_id(self, league: League, team_id: UUID, week: int | None = None) -> TeamOut:
        team = await self.teams.get(league.id, team_id)
        if team is None:
            raise NotFoundError("That team is not in this league.")
        return await self.team_out(league, team, week)

    # ---- matchup ---------------------------------------------------------------

    async def matchup_out(self, league: League, team: FantasyTeam, week: int | None = None) -> MatchupOut | None:
        week = week or league.current_week
        m = await self.matchups.get_for_team(league.id, week, team.id)
        if m is None:
            return None
        user_side = await self.team_out(league, team, week)
        user = MatchupSideOut(
            team=user_side.team, points=m.points, projected_points=user_side.projected_points, starters=user_side.starters
        )
        opponent: MatchupSideOut | None = None
        if m.opponent_team_id:
            opp_team = await self.teams.get(league.id, m.opponent_team_id)
            opp_m = await self.matchups.get_for_team(league.id, week, m.opponent_team_id)
            if opp_team:
                opp_view = await self.team_out(league, opp_team, week)
                opponent = MatchupSideOut(
                    team=opp_view.team,
                    points=opp_m.points if opp_m else 0.0,
                    projected_points=opp_view.projected_points,
                    starters=opp_view.starters,
                )
        if opponent is None:
            status = "bye"
        elif m.points == 0 and opponent.points == 0:
            status = "upcoming"
        elif week < league.current_week:
            status = "final"
        else:
            status = "in_progress"
        view = MatchupOut(
            week=week,
            is_bye=opponent is None,
            user=user,
            opponent=opponent,
            status=status,
            calls=_slot_calls(user, opponent),
            games=await self._nfl_games(league.season, week),
        )
        await self.attach_live_stat_lines(league, view)
        return view

    async def attach_live_stat_lines(self, league: League, view: MatchupOut) -> None:
        """Counting stats for starters whose NFL game is in progress this week."""
        if self.weekly_stats is None or view.week != league.current_week:
            return
        if not any(game.state == "in" for game in view.games):
            return
        blob = await self.weekly_stats.week(league.season, view.week, max_age=30)
        _apply_live_stat_lines(view, blob)

    async def _nfl_games(self, season: int, week: int) -> list[NflGameOut]:
        loader = getattr(self.nfl_data, "live_summaries", None)
        if loader is None:
            return []
        try:
            rows = await loader(season, week)
        except Exception as exc:  # noqa: BLE001 - the matchup still loads if the scoreboard does not
            log.warning("matchup.nfl_games_failed", error=str(exc))
            return []
        rank = {"in": 0, "pre": 1, "post": 2}
        ordered = sorted(enumerate(rows), key=lambda item: (rank.get(item[1].state or "", 3), item[0]))
        return [
            NflGameOut(
                away=game.away,
                home=game.home,
                away_score=game.away_score,
                home_score=game.home_score,
                state=game.state,
                detail=game.detail,
                summary=game.summary,
                broadcast=game.broadcast,
            )
            for _, game in ordered
        ]

    async def apply_live_matchup_points(self, league: League, view: MatchupOut, raw_sides: list[dict]) -> None:
        """Replace stored week points with the public Sleeper matchup that just came back."""
        sides: dict[str, MatchupSideOut] = {}
        user_team = await self.teams.get(league.id, view.user.team.id)
        if user_team:
            sides[user_team.external_team_id] = view.user
        if view.opponent:
            opponent_team = await self.teams.get(league.id, view.opponent.team.id)
            if opponent_team:
                sides[opponent_team.external_team_id] = view.opponent
        external_ids: set[str] = set()
        incoming: dict[str, dict] = {}
        for raw in raw_sides:
            roster_id = str(raw.get("roster_id"))
            if roster_id not in sides:
                continue
            incoming[roster_id] = raw
            external_ids.update(str(player_id) for player_id in (raw.get("players_points") or {}))
        mapped = await self.players.map_external_ids(league.provider, external_ids)
        for roster_id, raw in incoming.items():
            side = sides[roster_id]
            points_by_player: dict[str, float] = {}
            for external_id, value in (raw.get("players_points") or {}).items():
                player = mapped.get(str(external_id))
                if player is None:
                    continue
                try:
                    points_by_player[str(player.id)] = float(value)
                except (TypeError, ValueError):
                    continue
            try:
                side.points = float(raw.get("points") or 0)
            except (TypeError, ValueError):
                side.points = 0.0
            for slot in side.starters:
                if slot.player and str(slot.player.id) in points_by_player:
                    slot.points = points_by_player[str(slot.player.id)]
            row = await self.matchups.get_for_team(league.id, view.week, side.team.id)
            if row is not None:
                row.points = side.points
                row.player_points = points_by_player
        if view.opponent is None:
            view.status = "bye"
        elif view.user.points == 0 and view.opponent.points == 0:
            view.status = "upcoming"
        elif view.week < league.current_week:
            view.status = "final"
        else:
            view.status = "in_progress"
        await self.session.commit()

    # ---- standings / transactions ----------------------------------------------

    async def standings(self, league: League) -> list[StandingsRowOut]:
        teams = await self.teams.list_for_league(league.id)
        ordered = sorted(teams, key=lambda t: (-(t.wins + 0.5 * t.ties), -t.points_for))
        return [
            StandingsRowOut(**self.team_summary(t, league).model_dump(), rank=i + 1)
            for i, t in enumerate(ordered)
        ]

    async def recent_transactions(self, league: League, limit: int = 25) -> list[TransactionOut]:
        team = await self.user_team(league)
        rows = await self.transactions.list_recent(league.id, limit)
        return [self._tx_out(t, team) for t in rows]

    async def league_trades(self, league: League) -> list[TransactionOut]:
        team = await self.user_team(league)
        rows = await self.transactions.list_trades(league.id)
        return [self._tx_out(t, team) for t in rows]

    async def get_trade(self, league: League, transaction_id: UUID) -> TransactionOut:
        team = await self.user_team(league)
        row = await self.transactions.get(league.id, transaction_id)
        if row is None or row.type != "trade":
            raise NotFoundError("That trade is not in this league.")
        return self._tx_out(row, team)

    @staticmethod
    def _tx_out(t: Transaction, user_team: FantasyTeam | None) -> TransactionOut:
        team_ids = set(t.details.get("team_ids", []))
        return TransactionOut(
            id=t.id,
            type=t.type,
            status=t.status,
            week=t.week,
            created_at=t.created_at,
            adds=t.details.get("adds", []),
            drops=t.details.get("drops", []),
            team_names=t.details.get("team_names", []),
            faab_bid=t.details.get("faab_bid"),
            involves_user=bool(user_team and str(user_team.id) in team_ids),
            picks=pick_lines(t.details.get("draft_picks") or []),
        )

    # ---- roster needs & full context -----------------------------------------

    def roster_needs(self, league: League, team_view: TeamOut) -> RosterNeedsOut:
        max_size = league.roster_settings.get("max_roster_size")
        bench_and_lineup = team_view.starters + team_view.bench
        return compute_roster_needs(
            team_view.lineup_slots,
            bench_and_lineup + team_view.reserve,
            int(max_size) - int(league.roster_settings.get("reserve_slots") or 0) - int(league.roster_settings.get("taxi_slots") or 0)
            if max_size
            else None,
        )

    async def build_context(self, league: League, week: int | None = None) -> TeamContext:
        week = week or league.current_week
        team = await self.user_team(league)
        if team is None:
            raise NotFoundError("We could not find your team in this league.")
        team_view = await self.team_out(league, team, week)
        matchup = await self.matchup_out(league, team, week)
        needs = self.roster_needs(league, team_view)
        available = await self.available_players(league, limit=150, week=week)
        txs = await self.recent_transactions(league, limit=15)
        standings = await self.standings(league)
        roster_players = [s.player for s in team_view.starters + team_view.bench if s.player]
        return TeamContext(
            league_id=str(league.id),
            league_name=league.name,
            season=league.season,
            week=week,
            scoring_type=league.league_settings.get("scoring_type") or "Unknown",
            scoring_settings=league.scoring_settings,
            lineup_slots=team_view.lineup_slots,
            waiver_type=league.league_settings.get("waiver_type"),
            team=team_view,
            matchup=matchup,
            needs=needs,
            available=available,
            recent_transactions=txs,
            standings=standings,
            projections_available=any(p.projected_points is not None for p in roster_players),
            bye_weeks_available=any(p.bye_week is not None for p in roster_players),
        )


def _sim_detail(projection) -> dict[str, float]:
    if projection is None or projection.detail.get("vegas_ff") != 1:
        return {}
    return {key: float(value) for key, value in projection.detail.items()}


def _apply_live_stat_lines(view: MatchupOut, blob: dict) -> None:
    playing = {team for game in view.games if game.state == "in" for team in (game.away, game.home)}
    if not playing:
        return
    sides = [view.user, view.opponent] if view.opponent else [view.user]
    for side in sides:
        for slot in side.starters:
            player = slot.player
            if player is None or not player.nfl_team or player.nfl_team not in playing:
                continue
            sleeper_id = player.external_ids.get("sleeper")
            raw = blob.get(sleeper_id) if sleeper_id else None
            if not isinstance(raw, dict):
                continue
            slot.stat_line = summarize_stats(raw) or None


def _slot_calls(user: MatchupSideOut, opponent: MatchupSideOut | None) -> list[SlotCallOut]:
    if opponent is None:
        return []
    by_index = {slot.slot_index: slot for slot in opponent.starters if slot.slot_index is not None}
    rng = random.Random()
    calls: list[SlotCallOut] = []
    for slot in user.starters:
        if slot.slot_index is None or slot.player is None:
            continue
        other = by_index.get(slot.slot_index)
        if other is None or other.player is None:
            continue
        left = sims_for(slot.player.projection_detail, rng=rng)
        right = sims_for(other.player.projection_detail, rng=rng)
        if left is None or right is None:
            continue
        result = start_sit(left, right, slot.player.name, other.player.name)
        calls.append(
            SlotCallOut(
                slot_index=slot.slot_index,
                start_name=result["start"],
                win_prob=result["win_prob"],
                confidence=result["confidence"],
            )
        )
    return calls
