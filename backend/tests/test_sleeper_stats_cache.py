"""Per-week stats files and longer TTL for finished weeks."""

import json
import time
from pathlib import Path

import httpx
import pytest
import respx
from httpx import Response

from app.nfl_data.sleeper_stats import SleeperWeeklyStats

BASE = "https://sleeper.test/v1"


@pytest.fixture
def stats(tmp_path: Path) -> SleeperWeeklyStats:
    return SleeperWeeklyStats(tmp_path, BASE, ttl_seconds=60, past_ttl_seconds=86_400)


@respx.mock(base_url=BASE)
async def test_week_writes_one_file_per_week(respx_mock, stats: SleeperWeeklyStats, tmp_path: Path):
    respx_mock.get("/stats/nfl/regular/2026/3").mock(
        return_value=Response(200, json={"1": {"pts_ppr": 12.5}})
    )
    blob = await stats.week(2026, 3)
    assert blob["1"]["pts_ppr"] == 12.5
    path = tmp_path / "sleeper_stats_2026_w3.json"
    assert path.exists()
    stored = json.loads(path.read_text())
    assert stored["stats"]["1"]["pts_ppr"] == 12.5
    assert "fetched_at" in stored


@respx.mock(base_url=BASE)
async def test_past_week_keeps_disk_cache_past_default_ttl(
    respx_mock, stats: SleeperWeeklyStats, tmp_path: Path
):
    route = respx_mock.get("/stats/nfl/regular/2026/2").mock(
        return_value=Response(200, json={"9": {"rush_yd": 40}})
    )
    await stats.week(2026, 2, past=True)
    # Pretend the in-memory entry aged out of the short TTL but not the past TTL.
    key = (2026, 2)
    fetched, payload = stats._memory[key]
    stats._memory[key] = (fetched - 120, payload)
    path = tmp_path / "sleeper_stats_2026_w2.json"
    raw = json.loads(path.read_text())
    raw["fetched_at"] = time.time() - 120
    path.write_text(json.dumps(raw))

    again = await stats.week(2026, 2, past=True)
    assert again["9"]["rush_yd"] == 40
    assert route.call_count == 1


@respx.mock(base_url=BASE)
async def test_reads_legacy_season_file(respx_mock, stats: SleeperWeeklyStats, tmp_path: Path):
    legacy = tmp_path / "sleeper_stats_2026.json"
    legacy.write_text(
        json.dumps(
            {
                "weeks": {
                    "1": {"fetched_at": time.time(), "stats": {"7": {"rec": 3}}},
                }
            }
        )
    )
    blob = await stats.week(2026, 1, past=True)
    assert blob["7"]["rec"] == 3
    assert respx_mock.calls.call_count == 0


@respx.mock(base_url=BASE)
async def test_memory_hit_skips_network(respx_mock, stats: SleeperWeeklyStats):
    route = respx_mock.get("/stats/nfl/regular/2026/4").mock(
        return_value=Response(200, json={"2": {"pass_yd": 200}})
    )
    await stats.week(2026, 4)
    await stats.week(2026, 4)
    assert route.call_count == 1
