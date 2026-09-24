import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import respx
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient

from app.api.deps import AppState
from app.core.config import Settings
from app.main import create_app
from app.models import Base
from tests.fixtures import sleeper as sleeper_fixtures

SLEEPER_BASE = "https://sleeper.test/v1"


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        jwt_secret="test-secret-that-is-long-enough-for-hs256-0000",
        openai_api_key=None,
        gemini_api_key=None,
        groq_api_key=None,
        credentials_key=Fernet.generate_key().decode(),
        sleeper_base_url=SLEEPER_BASE,
        sleeper_graphql_url="https://sleeper.test/graphql",
        sleeper_player_cache_path=tmp_path / "players.json",
        nfl_data_file=tmp_path / "nfl_data.json",
        log_level="WARNING",
    )


@pytest.fixture
async def state(settings: Settings) -> AsyncIterator[AppState]:
    container = AppState(settings)
    async with container.db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield container
    await container.db.dispose()


@pytest.fixture
async def client(settings: Settings, state: AppState) -> AsyncIterator[AsyncClient]:
    app = create_app(settings, state)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.fixture
async def session(state: AppState):
    async with state.db.session_factory() as s:
        yield s


async def register(client: AsyncClient, email: str = "mike@example.com", name: str = "Mike") -> dict:
    resp = await client.post(
        "/api/auth/register", json={"email": email, "name": name, "password": "supersecret1"}
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict:
    return await register(client)


@pytest.fixture
def sleeper_mock():
    """respx router pre-loaded with a healthy Sleeper league."""
    with respx.mock(base_url=SLEEPER_BASE, assert_all_called=False) as router:
        sleeper_fixtures.install(router)
        yield router
