"""Builds enriched, provider-neutral views of a league for the API and AI tools.

Combines the normalized DB (fantasy platform data) with the NFLDataProvider
(bye weeks, projections, stats). Everything the intelligence layer consumes is
produced here.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.domain.enums import NON_LINEUP_SLOTS
from app.intelligence.context import TeamContext
from app.intelligence.lineup import lineup_issues, player_flags
from app.intelligence.roster_needs import compute_roster_needs
from app.models import FantasyTeam, League, Player, RosterEntry, Transaction
from app.nfl_data import NFLDataProvider, player_key
from app.nfl_data.headshot import headshot_url
from app.nfl_data.live import depth_for_player
from app.nfl_data.props import EspnPropClient, prop_components
from app.nfl_data.rankings import RankCandidate, build_rankings, ruled_out
from app.nfl_data.sleeper_stats import SleeperWeeklyStats
from app.nfl_data.vegas import explain_projection, normalize_position
from app.repositories import (
    MatchupRepository,
    PlayerRepository,
    RosterRepository,
    TeamRepository,
    TransactionRepository,
)
from app.schemas.league import (
    fantasy_account_out,
    LeagueDetailOut,
    LeagueOut,
    MatchupOut,
    MatchupSideOut,
    PlayerOut,
    PlayerSheetOut,
    PropLineOut,
    RankingRowOut,
    RankingsOut,
    RosterNeedsOut,
    RosterSlotOut,
    StandingsRowOut,
    TeamOut,
    TeamSummaryOut,
    TransactionOut,
)

log = get_logger(__name__)


class LeagueContextService:
    def __init__(
        self,
        session: AsyncSession,
        nfl_data: NFLDataProvider,
        weekly_stats: SleeperWeeklyStats | None = None,
        props: EspnPropClient | None = None,
    ):
        self.session = session
        self.nfl_data = nfl_data
        self.weekly_stats = weekly_stats
        self.props = props
        self.teams = TeamRepository(session)
        self.players = PlayerRepository(session)
        self.rosters = RosterRepository(session)
        self.matchups = MatchupRepository(session)
        self.transactions = TransactionRepository(session)

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
        """Saved number, then DraftKings props. Defenses still use the opponent's implied total."""
        key = player_key(player.name, player.position, player.nfl_team)
        projection = await self.nfl_data.get_projection(key, league.season, week)
        if projection is not None or on_bye:
            return projection
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
            return await self.nfl_data.project_from_line(
                nfl_team=player.nfl_team,
                position=player.position,
                depth=depth_for_player(player.extra),
                season=league.season,
                week=week,
                scoring=league.scoring_settings or {},
            )
        return None

    async def player_out(self, player: Player, league: League, week: int) -> PlayerOut:
        key = player_key(player.name, player.position, player.nfl_team)
        bye = await self.nfl_data.get_bye_week(player.nfl_team, league.season) if player.nfl_team else None
        opponent = await self.nfl_data.get_opponent(player.nfl_team, league.season, week) if player.nfl_team else None
        on_bye = bye == week if bye is not None else False
        if on_bye:
            opponent = None
        projection = await self._week_projection(player, league, week, on_bye)
        stats = await self.nfl_data.get_season_stats(key, league.season)
        schedule = await self.nfl_data.get_schedule(player.nfl_team, league.season) if player.nfl_team else []
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
            season_points=stats.fantasy_points if stats else None,
            points_per_game=stats.fantasy_points_per_game if stats else None,
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
        players = await self.players.search(
            provider=league.provider,
            exclude_ids=rostered,
            position=position,
            query=search,
            limit=limit,
        )
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

    async def search_players(
        self, league: League, *, search: str | None, position: str | None, limit: int, week: int | None = None
    ) -> list[PlayerOut]:
        week = week or league.current_week
        players = await self.players.search(
            provider=league.provider, position=position, query=search, limit=limit
        )
        return [await self.player_out(p, league, week) for p in players]

    async def rankings(self, league: League, week: int | None = None, position: str | None = None) -> RankingsOut:
        week = week or league.current_week
        raw = await self.players.list_active(league.provider, ("QB", "RB", "WR", "TE", "K", "DEF"))
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
                )
            )
        rows, notes = build_rankings(
            candidates,
            team_count=league.team_count,
            roster_positions=list(league.roster_positions),
            position=position,
        )
        return RankingsOut(
            week=week,
            notes=notes,
            rows=[
                RankingRowOut(
                    rank=row.rank,
                    player_id=UUID(row.player.player_id),
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
        return MatchupOut(week=week, is_bye=opponent is None, user=user, opponent=opponent, status=status)

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
