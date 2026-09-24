# Architecture

This document records the design produced before implementation and the
architectural decisions made along the way.

## 1. Repository structure

```text
fantasy_ai/
├── backend/
│   ├── alembic/                    # migrations (env.py + versions/)
│   ├── alembic.ini
│   ├── app/
│   │   ├── main.py                 # FastAPI app factory, exception handlers
│   │   ├── core/                   # config, logging, security (JWT/bcrypt), errors
│   │   ├── db/                     # SQLAlchemy base + async session factory
│   │   ├── models/                 # SQLAlchemy ORM models (normalized schema)
│   │   ├── schemas/                # Pydantic API request/response schemas
│   │   ├── domain/                 # Provider-neutral DTOs + Recommendation model
│   │   ├── providers/              # FantasyProvider ABC, registry, adapters
│   │   │   ├── base.py
│   │   │   ├── registry.py
│   │   │   ├── sleeper/            # client.py (HTTP), mappers.py, provider.py
│   │   │   ├── yahoo.py            # stub
│   │   │   ├── espn.py             # stub
│   │   │   └── nfl.py              # stub
│   │   ├── nfl_data/               # NFLDataProvider interface + local-file impl
│   │   ├── repositories/           # DB access, one module per aggregate
│   │   ├── services/               # Use cases: connect, import, sync, queries, demo
│   │   ├── intelligence/           # Deterministic fantasy logic (no LLM)
│   │   ├── ai/                     # LLM client, tools, agent loop, analysis, chat
│   │   ├── api/                    # deps.py + routes/
│   │   └── seed/                   # demo league data generator
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/app/                    # Next.js App Router pages
│   ├── src/components/             # UI + feature components
│   ├── src/lib/                    # api client, types, auth, league context
│   ├── src/__tests__/              # Vitest
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── docs/ARCHITECTURE.md
└── README.md
```

Layering rule (enforced by import direction):

```text
api/routes  ->  services  ->  repositories  ->  models
                   |   \
                   |    -> providers (FantasyProvider) -> external HTTP
                   |    -> nfl_data  (NFLDataProvider) -> external HTTP / files
                   -> intelligence (pure functions over domain/ORM data)
ai/tools    ->  services + intelligence   (never providers, never raw Sleeper)
```

The AI layer only sees normalized data through services. Providers only
produce normalized DTOs from `app/domain`. The frontend only talks to the
FastAPI API.

## 2. Database schema

All primary keys are UUIDs. JSON columns are portable `JSON` (native JSONB on
Postgres is an optimisation for later). Timestamps are timezone-aware UTC.

```text
users
  id, email (unique), name, hashed_password, created_at

fantasy_accounts
  id, user_id -> users, provider (sleeper|yahoo|espn|nfl|demo),
  external_user_id, username, display_name, avatar,
  encrypted_credentials (nullable; for OAuth tokens later),
  created_at, last_synced_at
  unique(user_id, provider, external_user_id)

leagues
  id, fantasy_account_id -> fantasy_accounts, provider, external_league_id,
  name, season, team_count, current_week, status,
  scoring_settings JSON, roster_settings JSON   # roster_positions + limits
  league_settings JSON                          # waiver type, FAAB budget, playoff info
  last_synced_at, sync_status (idle|syncing|success|error), sync_error,
  created_at, updated_at
  unique(fantasy_account_id, external_league_id)

fantasy_teams
  id, league_id -> leagues, external_team_id, owner_external_id, owner_name,
  name, avatar, wins, losses, ties, points_for, points_against,
  faab_remaining, waiver_position, settings JSON
  unique(league_id, external_team_id)

players                                          # INTERNAL identity
  id, name, first_name, last_name, position, fantasy_positions JSON,
  nfl_team, status, injury_status, injury_body_part, age, years_exp,
  created_at, updated_at

player_external_ids                              # provider mapping
  id, player_id -> players, provider, external_id
  unique(provider, external_id)

roster_entries
  id, fantasy_team_id -> fantasy_teams, player_id -> players,
  week, roster_slot, is_starter, slot_index
  unique(fantasy_team_id, player_id, week)

matchups
  id, league_id -> leagues, week, external_matchup_id,
  team_id -> fantasy_teams, opponent_team_id -> fantasy_teams (nullable = bye),
  points, projected_points (nullable), player_points JSON
  unique(league_id, week, team_id)

transactions
  id, league_id -> leagues, external_transaction_id, type, status, week,
  created_at (provider time), metadata JSON (adds, drops, faab, teams)
  unique(league_id, external_transaction_id)
```

Decision: `Player` is provider-neutral. Provider IDs live only in
`player_external_ids`. The spec's `provider`/`external_player_id` fields on
Player are expressed through that table so one internal player can carry a
Sleeper ID, a Yahoo ID, an ESPN ID and an NFL ID simultaneously.

## 3. API routes

```text
GET  /api/health

POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me

GET  /api/integrations/accounts
POST /api/integrations/sleeper/connect                  {username}
GET  /api/integrations/sleeper/leagues?season=
POST /api/integrations/sleeper/leagues/{external_league_id}/import

GET  /api/leagues
GET  /api/leagues/{league_id}
GET  /api/leagues/{league_id}/team
GET  /api/leagues/{league_id}/matchup?week=
GET  /api/leagues/{league_id}/players?position=&search=&available=&limit=
GET  /api/leagues/{league_id}/standings
GET  /api/leagues/{league_id}/transactions?limit=
GET  /api/leagues/{league_id}/recommendations
GET  /api/leagues/{league_id}/briefing
POST /api/leagues/{league_id}/sync

POST /api/leagues/{league_id}/ai/analyze
POST /api/leagues/{league_id}/ai/chat                  {messages:[...]}
POST /api/leagues/{league_id}/ai/trade                 {give:[player_id], receive:[player_id]}

GET  /api/players/{player_id}
POST /api/demo/league                                    seeds 12-team PPR demo league
```

Every `/api/leagues/{league_id}/...` route resolves the league through
`get_owned_league`, which joins `leagues -> fantasy_accounts -> users` and
404s when the league is not owned by the caller.

## 4. Provider interface

```python
class FantasyProvider(ABC):
    provider: Provider                       # enum
    capabilities: ProviderCapabilities       # auth_type, supports_available_players, ...

    async def get_state(self) -> ProviderState                      # season, current week
    async def get_user(self, identifier: str) -> ProviderUser
    async def get_leagues(self, external_user_id: str, season: int) -> list[LeagueSummary]
    async def get_league(self, league_id: str) -> LeagueDetails
    async def get_teams(self, league_id: str) -> list[TeamData]
    async def get_rosters(self, league_id: str) -> list[RosterData]
    async def get_matchups(self, league_id: str, week: int) -> list[MatchupData]
    async def get_transactions(self, league_id: str, week: int) -> list[TransactionData]
    async def get_players(self) -> dict[str, PlayerData]
    async def get_available_players(self, league_id: str) -> list[PlayerData]
```

All return types are provider-neutral DTOs from `app/domain`. Sleeper-specific
JSON never leaves `app/providers/sleeper`. Providers raise a small family of
`ProviderError` subclasses (`ProviderNotFound`, `ProviderRateLimited`,
`ProviderUnavailable`, `ProviderAuthError`) that the API maps to
404/429/502/401.

`YahooProvider`, `ESPNProvider`, `NFLFantasyProvider` implement the interface
and raise `ProviderNotImplemented`; their capabilities declare `auth_type =
"oauth"` / `"cookie"` so the frontend can render the right connect flow later.
`FantasyAccount.encrypted_credentials` (Fernet, key from `CREDENTIALS_KEY`)
stores the Sleeper account token used for lineup writes, and is where OAuth
tokens will live. The scoring write is `update_matchup_leg` on
`https://sleeper.com/graphql`, confirmed by re-reading `matchup_legs`.
`roster_update_starters` is not used. The public matchup endpoint is also
re-read, but it is cached and is not treated as proof the write failed.

Separately, `NFLDataProvider` (`app/nfl_data`) supplies projections, bye weeks
and news. The default `LocalFileNFLDataProvider` reads `data/nfl_data.json`
and returns `None` for anything it does not know, so the intelligence layer
and the LLM report "unavailable" rather than inventing numbers.

## 5. AI tool architecture

```text
POST /ai/chat | /ai/analyze
        |
   ToolContext(session, user, league, team, week)   <- built from the authorized league
        |
   Agent loop (max N rounds)
        |-> LLMClient.complete(messages, tools, response_format)
        |<- tool_calls -> ToolRegistry.execute(name, args, ctx)
        |       each tool: Pydantic-validated args, reads ONLY through ctx
        |-> final message (free text for chat, JSON schema for analysis)
```

Tools (`app/ai/tools`): `get_team`, `get_roster`, `get_league_settings`,
`get_current_matchup`, `get_player`, `get_player_stats`,
`get_available_players`, `get_recent_transactions`, `compare_players`,
`get_roster_needs`, `get_standings`, `get_recommendations`.

Authorization is structural: tools receive a `ToolContext` that was created
from an already-authorized league. A tool cannot name another league, and
player lookups are scoped to players that exist in the context league.

Deterministic work (lineup legality, eligibility, needs, bye/injury flags,
projections, recommendations) lives in `app/intelligence` and is exposed to
the model through tools. The model interprets and explains; it does not
compute.

`LLMClient` has two implementations: `OpenAIClient` and a
`DeterministicFallback` used when `OPENAI_API_KEY` is unset (and in tests),
which converts the rule-based recommendations into the same structured
`TeamAnalysis` shape. This keeps the demo usable offline.

Structured outputs use OpenAI JSON-schema `response_format` generated from the
Pydantic `TeamAnalysis` / `TradeAnalysis` models and are re-validated
server-side.

## 6. Implementation plan

Phase 1 — skeleton: FastAPI + SQLAlchemy async + Alembic + JWT auth, Next.js
shell, Docker Compose, demo seed.
Phase 2 — Sleeper: client with retries, mappers -> DTOs, connect/list/import,
idempotent sync.
Phase 3 — Dashboard, team, matchup, players, standings, transactions views.
Phase 4 — Tools + agent loop + "Analyze My Team" structured output.
Phase 5 — Chat.
Phase 6 — Briefing, start/sit, waiver, trade analysis (deterministic +
narrative).
Phase 7 — Provider stubs with capabilities and encrypted credential storage.

## Other decisions

* **SQLite for tests and optional local dev.** Postgres is the production
  target (docker-compose). The ORM uses only portable types so the same code
  runs on `sqlite+aiosqlite` in tests with no external service.
* **Stateless chat.** The client sends the conversation window; the server
  does not persist chat history in the MVP.
* **Sleeper player catalogue caching.** `/players/nfl` is ~5 MB. It is cached
  on disk for 24h and only fantasy-relevant active players plus every rostered
  player are persisted to the DB.
* **Roster slots.** Sleeper gives `starters` as an ordered list aligned with
  `roster_positions`. Slot names are derived from that alignment; bench
  players are `BN`, `reserve` -> `IR`, `taxi` -> `TAXI`.
* **Idempotent sync.** All writes are upserts keyed on natural unique
  constraints; roster entries for a (team, week) are replaced atomically.
