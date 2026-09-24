from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError
from app.core.logging import get_logger
from app.domain.enums import Provider, SyncStatus
from app.models import League
from app.nfl_data import LocalFileNFLDataProvider, NFLDataProvider
from app.repositories import FantasyAccountRepository, LeagueRepository
from app.seed.demo_league import DEMO_LEAGUE_ID, DEMO_USER, build_snapshot
from app.services.sync_service import SyncService

log = get_logger(__name__)


class DemoService:
    def __init__(self, session: AsyncSession, nfl_data: NFLDataProvider, enabled: bool = True):
        self.session = session
        self.nfl_data = nfl_data
        self.enabled = enabled

    async def create_demo_league(self, user_id: UUID) -> League:
        """Attach the fake 12-team PPR league to the user. Idempotent."""
        if not self.enabled:
            raise ForbiddenError("Demo mode is disabled on this server.")
        snapshot, nfl_data = build_snapshot()

        accounts = FantasyAccountRepository(self.session)
        leagues = LeagueRepository(self.session)
        account = await accounts.upsert(user_id, Provider.DEMO.value, DEMO_USER)

        league = await leagues.get_by_identity(account.id, DEMO_LEAGUE_ID)
        if league is None:
            league = League(
                fantasy_account_id=account.id,
                provider=Provider.DEMO.value,
                external_league_id=DEMO_LEAGUE_ID,
                name=snapshot.league.name,
                season=snapshot.league.season,
                team_count=snapshot.league.team_count,
                current_week=snapshot.league.current_week,
                scoring_settings={},
                roster_settings={},
                league_settings={},
            )
            leagues.add(league)
            await self.session.flush()
            league.fantasy_account = account

        await SyncService(self.session).apply_snapshot(league, snapshot)
        league.sync_status = SyncStatus.SUCCESS
        league.last_synced_at = datetime.now(UTC)
        await self.session.commit()

        if isinstance(self.nfl_data, LocalFileNFLDataProvider):
            self.nfl_data.merge(nfl_data)
        log.info("demo.league_created", user_id=str(user_id), league_id=str(league.id))
        return league
