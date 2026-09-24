"""Sleeper HTTP client error handling (all HTTP mocked with respx)."""

import httpx
import pytest
import respx
from httpx import Response

from app.core.errors import ProviderNotFound, ProviderRateLimited, ProviderUnavailable
from app.providers.sleeper import SleeperClient, SleeperProvider

BASE = "https://sleeper.test/v1"


def make_client(tmp_path) -> SleeperClient:
    return SleeperClient(base_url=BASE, timeout=1.0, max_retries=1, player_cache_path=tmp_path / "p.json")


@respx.mock(base_url=BASE)
async def test_invalid_username_null_body_raises_not_found(respx_mock, tmp_path):
    respx_mock.get("/user/ghost").mock(return_value=Response(200, json=None))
    with pytest.raises(ProviderNotFound):
        await SleeperProvider(make_client(tmp_path)).get_user("ghost")


@respx.mock(base_url=BASE)
async def test_404_raises_not_found(respx_mock, tmp_path):
    respx_mock.get("/league/000").mock(return_value=Response(404))
    with pytest.raises(ProviderNotFound):
        await make_client(tmp_path).get_league("000")


@respx.mock(base_url=BASE)
async def test_rate_limit_after_retries(respx_mock, tmp_path):
    route = respx_mock.get("/state/nfl").mock(return_value=Response(429))
    with pytest.raises(ProviderRateLimited):
        await make_client(tmp_path).get_state()
    assert route.call_count == 2  # initial + 1 retry


@respx.mock(base_url=BASE)
async def test_network_error_raises_unavailable(respx_mock, tmp_path):
    respx_mock.get("/state/nfl").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(ProviderUnavailable):
        await make_client(tmp_path).get_state()


@respx.mock(base_url=BASE)
async def test_retry_then_success(respx_mock, tmp_path):
    route = respx_mock.get("/state/nfl")
    route.side_effect = [Response(503), Response(200, json={"season": "2026", "week": 4})]
    state = await make_client(tmp_path).get_state()
    assert state["week"] == 4
    assert route.call_count == 2


@respx.mock(base_url=BASE)
async def test_players_cached_on_disk_and_memory(respx_mock, tmp_path):
    route = respx_mock.get("/players/nfl").mock(return_value=Response(200, json={"1": {"player_id": "1"}}))
    client = make_client(tmp_path)
    await client.get_players()
    await client.get_players()
    assert route.call_count == 1
    assert (tmp_path / "p.json").exists()
    # A fresh client reads the disk cache without hitting the network.
    fresh = make_client(tmp_path)
    await fresh.get_players()
    assert route.call_count == 1


@respx.mock(base_url=BASE)
async def test_empty_league_list_returns_empty(respx_mock, tmp_path):
    respx_mock.get("/user/1/leagues/nfl/2026").mock(return_value=Response(200, json=None))
    assert await make_client(tmp_path).get_user_leagues("1", 2026) == []
