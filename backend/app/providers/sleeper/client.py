"""Thin async HTTP client for the public Sleeper API.

Responsibilities: URL building, retries/backoff, error translation and caching
of the very large player catalogue. It returns raw JSON; app.providers.sleeper.mappers
turns that into normalized DTOs.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx

from app.core.errors import ProviderNotFound, ProviderRateLimited, ProviderUnavailable
from app.core.logging import get_logger

log = get_logger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class SleeperClient:
    PROVIDER = "sleeper"

    def __init__(
        self,
        base_url: str = "https://api.sleeper.app/v1",
        timeout: float = 15.0,
        max_retries: int = 3,
        player_cache_path: Path | None = None,
        player_cache_ttl_seconds: int = 24 * 3600,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.player_cache_path = player_cache_path
        self.player_cache_ttl_seconds = player_cache_ttl_seconds
        self._transport = transport
        self._players_memo: tuple[float, dict[str, Any]] | None = None

    # ---- low level ------------------------------------------------------------

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=self._transport,
            headers={"User-Agent": "fantasy-ai/0.1 (+https://github.com)"},
        )

    async def _get(self, path: str, *, allow_null: bool = False) -> Any:
        last_exc: Exception | None = None
        async with self._client() as client:
            for attempt in range(self.max_retries + 1):
                try:
                    resp = await client.get(path)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last_exc = exc
                    log.warning("sleeper.transport_error", path=path, attempt=attempt, error=str(exc))
                else:
                    if resp.status_code == 404:
                        raise ProviderNotFound(
                            "Sleeper could not find that resource.", provider=self.PROVIDER
                        )
                    if resp.status_code in RETRYABLE_STATUS:
                        last_exc = httpx.HTTPStatusError(
                            f"status {resp.status_code}", request=resp.request, response=resp
                        )
                        if resp.status_code == 429 and attempt == self.max_retries:
                            raise ProviderRateLimited(provider=self.PROVIDER)
                        log.warning("sleeper.retryable_status", path=path, status=resp.status_code)
                    elif resp.status_code >= 400:
                        raise ProviderUnavailable(
                            f"Sleeper returned HTTP {resp.status_code}.", provider=self.PROVIDER
                        )
                    else:
                        try:
                            body = resp.content.strip()
                            data = None if body in (b"", b"null") else json.loads(body)
                        except json.JSONDecodeError as exc:
                            raise ProviderUnavailable(
                                "Sleeper returned an unreadable response.", provider=self.PROVIDER
                            ) from exc
                        if data is None and not allow_null:
                            # Sleeper returns `null` with 200 for unknown users/leagues.
                            raise ProviderNotFound(
                                "Sleeper could not find that resource.", provider=self.PROVIDER
                            )
                        return data
                if attempt < self.max_retries:
                    await asyncio.sleep(0.4 * (2**attempt))
        if isinstance(last_exc, httpx.HTTPStatusError) and last_exc.response.status_code == 429:
            raise ProviderRateLimited(provider=self.PROVIDER)
        raise ProviderUnavailable(
            "Sleeper could not be reached. Please try again.", provider=self.PROVIDER
        ) from last_exc

    # ---- endpoints ------------------------------------------------------------

    async def get_state(self) -> dict[str, Any]:
        return await self._get("/state/nfl")

    async def get_user(self, username_or_id: str) -> dict[str, Any]:
        return await self._get(f"/user/{username_or_id}")

    async def get_user_leagues(self, user_id: str, season: int) -> list[dict[str, Any]]:
        return await self._get(f"/user/{user_id}/leagues/nfl/{season}", allow_null=True) or []

    async def get_league(self, league_id: str) -> dict[str, Any]:
        return await self._get(f"/league/{league_id}")

    async def get_rosters(self, league_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/rosters", allow_null=True) or []

    async def get_league_users(self, league_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/users", allow_null=True) or []

    async def get_matchups(self, league_id: str, week: int) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/matchups/{week}", allow_null=True) or []

    async def get_transactions(self, league_id: str, week: int) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/transactions/{week}", allow_null=True) or []

    async def get_players(self) -> dict[str, Any]:
        """The full NFL player catalogue (~5MB). Cached in memory and on disk."""
        now = time.time()
        if self._players_memo and now - self._players_memo[0] < self.player_cache_ttl_seconds:
            return self._players_memo[1]

        cached = self._read_disk_cache(now)
        if cached is not None:
            self._players_memo = (now, cached)
            return cached

        log.info("sleeper.fetch_players")
        data = await self._get("/players/nfl")
        if not isinstance(data, dict):
            raise ProviderUnavailable("Sleeper players payload was malformed.", provider=self.PROVIDER)
        self._players_memo = (now, data)
        self._write_disk_cache(data)
        return data

    # ---- cache helpers -------------------------------------------------------

    def _read_disk_cache(self, now: float) -> dict[str, Any] | None:
        path = self.player_cache_path
        if not path or not path.exists():
            return None
        try:
            if now - path.stat().st_mtime > self.player_cache_ttl_seconds:
                return None
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None

    def _write_disk_cache(self, data: dict[str, Any]) -> None:
        path = self.player_cache_path
        if not path:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(data, fh)
            tmp.replace(path)
        except OSError as exc:
            log.warning("sleeper.player_cache_write_failed", error=str(exc))
