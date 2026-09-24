"""Authenticated client for the Sleeper web app's private GraphQL API.

Sleeper publishes no schema docs. The scoring lineup is `update_matchup_leg`.
`roster_update_starters` persists and returns success without changing what
scores, so this client never calls it.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.errors import ProviderAuthError, ProviderError, ProviderUnavailable
from app.core.logging import get_logger

log = get_logger(__name__)

WHOAMI_QUERY = "query { me { user_id username display_name } }"

SET_SCORING_LINEUP = """
mutation($round: Int!, $leg: Int!, $league_id: Snowflake!, $roster_id: Int!, $starters: [String]) {
  update_matchup_leg(round: $round, leg: $leg, league_id: $league_id, roster_id: $roster_id, starters: $starters) {
    roster_id
    starters
  }
}
""".strip()

READ_SCORING_LINEUPS = """
query($round: Int!, $league_id: Snowflake!) {
  matchup_legs(round: $round, league_id: $league_id) {
    roster_id
    starters
  }
}
""".strip()

# IR is the roster reserve list, not a scoring-lineup slot. This is the mutation
# the Sleeper app uses. It is not roster_update_starters.
SET_RESERVE = """
mutation($league_id: Snowflake!, $roster_id: Int!, $reserve: [String]) {
  roster_update_reserve(league_id: $league_id, roster_id: $roster_id, reserve: $reserve) {
    roster_id
    reserve
  }
}
""".strip()

READ_ROSTERS = """
query($league_id: Snowflake!) {
  league_rosters(league_id: $league_id) {
    roster_id
    reserve
    starters
  }
}
""".strip()

USER_AGENT = "fantasy-ai/0.1 (+https://github.com)"


@dataclass(frozen=True)
class SleeperIdentity:
    user_id: str
    username: str
    display_name: str | None


class SleeperGraphQL:
    def __init__(self, url: str, token: str | None = None, timeout: float = 15.0):
        self.url = url
        self.token = token
        self.timeout = timeout

    async def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        # The web app sends the raw JWT. A "Bearer " prefix is rejected.
        if self.token:
            headers["Authorization"] = self.token
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.url, json={"query": query, "variables": variables or {}}, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            log.warning("sleeper.graphql_transport_error", error=type(exc).__name__)
            raise ProviderUnavailable("Could not reach Sleeper.", provider="sleeper") from exc

        if resp.status_code in (401, 403):
            raise ProviderAuthError(
                "Sleeper rejected the token. Paste a fresh one from the web app.", provider="sleeper"
            )
        if resp.status_code >= 400:
            raise ProviderUnavailable(f"Sleeper returned HTTP {resp.status_code}.", provider="sleeper")
        try:
            body = resp.json()
        except ValueError as exc:
            raise ProviderUnavailable("Sleeper returned an unreadable response.", provider="sleeper") from exc
        if not isinstance(body, dict):
            raise ProviderError("Sleeper returned an unreadable response.", provider="sleeper")

        errors = body.get("errors") or []
        if errors:
            message = _error_message(errors)
            lowered = message.lower()
            if any(phrase in lowered for phrase in ("unauthorized", "not authenticated", "invalid token")):
                raise ProviderAuthError(
                    "Sleeper rejected the token. Paste a fresh one from the web app.", provider="sleeper"
                )
            raise ProviderError(message or "Sleeper rejected the request.", provider="sleeper")

        data = body.get("data")
        if not isinstance(data, dict):
            raise ProviderError("Sleeper returned an empty response.", provider="sleeper")
        return data

    async def whoami(self) -> SleeperIdentity:
        data = await self.execute(WHOAMI_QUERY)
        me = data.get("me")
        if not isinstance(me, dict) or not me.get("user_id"):
            raise ProviderAuthError(
                "Sleeper rejected the token. Paste a fresh one from the web app.", provider="sleeper"
            )
        return SleeperIdentity(
            user_id=str(me["user_id"]),
            username=str(me.get("username") or ""),
            display_name=me.get("display_name"),
        )

    async def set_scoring_lineup(
        self, *, week: int, league_id: str, roster_id: int, starters: list[str]
    ) -> None:
        await self.execute(
            SET_SCORING_LINEUP,
            {
                "round": week,
                "leg": week,
                "league_id": league_id,
                "roster_id": roster_id,
                "starters": starters,
            },
        )

    async def read_scoring_lineup(self, *, week: int, league_id: str, roster_id: int) -> list[str] | None:
        """Return the scoring starters for one roster, or None if that roster is absent."""
        data = await self.execute(READ_SCORING_LINEUPS, {"round": week, "league_id": league_id})
        legs = data.get("matchup_legs")
        if not isinstance(legs, list):
            raise ProviderError("Sleeper did not return scoring lineups.", provider="sleeper")
        for leg in legs:
            if isinstance(leg, dict) and str(leg.get("roster_id")) == str(roster_id):
                starters = leg.get("starters")
                if not isinstance(starters, list):
                    return None
                return [str(s) for s in starters]
        return None

    async def set_reserve(self, *, league_id: str, roster_id: int, reserve: list[str]) -> None:
        await self.execute(
            SET_RESERVE,
            {"league_id": league_id, "roster_id": roster_id, "reserve": reserve},
        )

    async def read_reserve(self, *, league_id: str, roster_id: int) -> list[str] | None:
        data = await self.execute(READ_ROSTERS, {"league_id": league_id})
        rosters = data.get("league_rosters")
        if not isinstance(rosters, list):
            raise ProviderError("Sleeper did not return rosters.", provider="sleeper")
        for roster in rosters:
            if isinstance(roster, dict) and str(roster.get("roster_id")) == str(roster_id):
                reserve = roster.get("reserve") or []
                if not isinstance(reserve, list):
                    return None
                return [str(player_id) for player_id in reserve if player_id]
        return None


def _error_message(errors: list) -> str:
    first = errors[0]
    if isinstance(first, dict):
        return str(first.get("message") or "Sleeper rejected the request.")
    return str(first)
