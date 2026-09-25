# OMAHA

An AI-powered fantasy football manager. Connect a fantasy league, see your team,
matchup, waivers and standings in one dashboard, and ask an AI assistant
questions that are answered from your **actual league data** via tool calling.

Sleeper is fully supported. Yahoo, ESPN and NFL Fantasy are designed for and
stubbed behind the same `FantasyProvider` interface.

```text
Sleeper username -> leagues -> import -> normalized DB -> dashboard -> "Analyze My Team"
```

---

## Contents

- [Architecture overview](#architecture-overview)
- [Tech stack](#tech-stack)
- [Quick start (Docker)](#quick-start-docker)
- [Local setup without Docker](#local-setup-without-docker)
- [Environment variables](#environment-variables)
- [Database migrations](#database-migrations)
- [Running the backend](#running-the-backend)
- [Running the frontend](#running-the-frontend)
- [Running tests](#running-tests)
- [Demo mode](#demo-mode)
- [Sleeper integration](#sleeper-integration)
- [AI architecture](#ai-architecture)
- [Deterministic logic vs AI](#deterministic-logic-vs-ai)
- [How to add another FantasyProvider](#how-to-add-another-fantasyprovider)
- [API reference](#api-reference)
- [Security notes](#security-notes)
- [Project layout](#project-layout)

---

## Architecture overview

```text
┌──────────────┐   HTTPS/JSON   ┌──────────────────────────────────────────────────┐
│  Next.js UI  │ ─────────────► │ FastAPI                                          │
│  (browser)   │ ◄───────────── │  api/routes ─► services ─► repositories ─► DB    │
└──────────────┘                │                 │   │                            │
                                │                 │   └─► providers/ (Sleeper, …)  │──► Sleeper API
                                │                 │                                │
                                │                 └─► nfl_data/ (projections,      │──► file / future feeds
                                │                     byes, news)                  │
                                │                                                  │
                                │  ai/ (tools ─► services, agent loop, OpenAI)     │──► OpenAI
                                └──────────────────────────────────────────────────┘
                                                        │
                                                   PostgreSQL
```

Key ideas:

* **Normalized domain model.** Providers translate their payloads into
  provider‑neutral DTOs (`app/domain/provider_models.py`); the DB, API, and AI
  only ever see normalized `League`, `FantasyTeam`, `Player`, `RosterEntry`,
  `Matchup`, `Transaction` rows.
* **Internal player identity.** `players` is provider‑neutral;
  `player_external_ids` maps `(provider, external_id)` to it, so a player can
  carry Sleeper, Yahoo, ESPN and NFL ids at once.
* **Two data planes.** `FantasyProvider` = league/roster data from the fantasy
  platform. `NFLDataProvider` = projections/byes/news from an NFL data source.
  Missing data is reported as unavailable, never fabricated.
* **Deterministic intelligence layer** (`app/intelligence`) computes lineup
  legality, eligibility, depth grades, injuries, byes, swaps and rule-based
  recommendations. The LLM explains; it does not compute.
* **Tool-calling AI** (`app/ai`) with a `ToolContext` bound to exactly one
  authorized league. No DB dumps in prompts.
* **Offline fallback.** With no Gemini, Groq, or OpenAI key, "Analyze My Team", chat,
  trade and briefing endpoints return rule-based output in the same schemas, so
  the whole product is usable in demo mode. A free Gemini key lets chat write
  this week's Sleeper lineup through the same confirmed scoring update as the dashboard.

The full design (schema, routes, provider interface, tool architecture,
decisions) is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Tech stack

| Layer     | Tech                                                                 |
|-----------|----------------------------------------------------------------------|
| Frontend  | Next.js 15 (App Router), TypeScript, Tailwind, TanStack Query, Vitest |
| Backend   | Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2, httpx, structlog |
| AI        | Gemini (free), Groq, or OpenAI chat completions with function calling |
| Database  | PostgreSQL 16 (SQLite supported for tests / quick local dev)          |
| Dev       | Docker Compose, pytest + respx (HTTP mocking)                         |

## Quick start (Docker)

```bash
git clone <repo> fantasy_ai && cd fantasy_ai
cp .env.example .env
# edit .env: set JWT_SECRET (any long random string) and optionally GEMINI_API_KEY
docker compose up --build
```

* Frontend: <http://localhost:3000>
* API docs: <http://localhost:8000/api/docs>
* Health: <http://localhost:8000/api/health>

The backend container runs `alembic upgrade head` on start. Create an account
in the UI, then either **Connect Sleeper** or **Load demo league**.

## Local setup without Docker

Requirements: Python 3.12+, Node 20+, and either PostgreSQL 14+ or nothing
(SQLite fallback).

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"

# Option A: Postgres
export DATABASE_URL=postgresql+asyncpg://fantasy:fantasy@localhost:5432/fantasy_ai
# Option B: SQLite (zero setup)
export DATABASE_URL=sqlite+aiosqlite:///./dev.db

export JWT_SECRET=$(openssl rand -hex 32)
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

On PowerShell use `$env:DATABASE_URL="sqlite+aiosqlite:///./dev.db"` etc.
Settings are also read from a `.env` in the repo root or `backend/`.

### Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open <http://localhost:3000>.

## Environment variables

See [`.env.example`](.env.example). The important ones:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLAlchemy async URL. `postgresql+asyncpg://…` or `sqlite+aiosqlite:///…` |
| `JWT_SECRET` | HS256 secret for access tokens. Use ≥32 random chars. |
| `GEMINI_API_KEY` | Free assistant (Google AI Studio). Enables lineup changes in chat. |
| `GROQ_API_KEY` | Free assistant used when `GEMINI_API_KEY` is empty. |
| `OPENAI_API_KEY` | Paid assistant used only when both free keys are empty. |
| `OPENAI_MODEL` | Default `gpt-4o-mini`. Any model supporting tools + JSON schema output. |
| `CREDENTIALS_KEY` | Fernet key for encrypting OAuth tokens (future providers). |
| `FRONTEND_URL` | Allowed CORS origin. |
| `DEMO_ENABLED` | Allow `POST /api/demo/league`. |
| `SLEEPER_PLAYER_CACHE_TTL_HOURS` | On-disk cache TTL for Sleeper's ~5 MB player catalogue. |
| `NEXT_PUBLIC_API_URL` | Frontend → backend base URL (the only frontend variable). |

No API keys are ever sent to the browser; the frontend only knows the API URL.

## Database migrations

Alembic (async) lives in `backend/alembic`.

```bash
cd backend
alembic upgrade head                      # apply
alembic revision --autogenerate -m "msg"  # after changing app/models
alembic downgrade -1
```

`alembic/env.py` reads `DATABASE_URL` from settings, so the same commands work
for Postgres and SQLite (batch mode is enabled automatically for SQLite).

## Running the backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Structured logs (structlog) print one line per request with `request_id`,
status and duration. Set `ENVIRONMENT=production` for JSON logs.

## Running the frontend

```bash
cd frontend
npm run dev        # dev server
npm run build && npm start   # production
npm run typecheck
```

## Running tests

Backend (48 tests, no network, SQLite in a temp dir, Sleeper mocked with respx):

```bash
cd backend
pytest -q
```

Covers: Sleeper normalization, invalid username, league import, roster
normalization, player mapping, league authorization, sync idempotency, sync
error tracking, rate-limit/network handling, AI tool authorization, agent tool
loop, structured-output validation and retry, deterministic fallbacks, demo
seed.

Frontend (Vitest + Testing Library):

```bash
cd frontend
npm test
```

## Demo mode

Click **Load demo league** (dashboard empty state or Settings) or
`POST /api/demo/league`. It creates a fictional 12‑team PPR league attached to
your account with:

* a user-controlled team (`Gridiron Gurus`), 12 teams, standings, weeks 1–4
  matchups, ~240 fictional players, available free agents, transactions;
* storylines: WR2 questionable, starting TE on bye, a bench RB out, a WR on IR;
* projections, season stats, bye weeks and news written to
  `backend/data/nfl_data.json` for the `LocalFileNFLDataProvider`.

The seed produces the same `ImportedLeagueSnapshot` a real provider returns and
runs through the same idempotent `SyncService`, so it exercises the real code
path. Every screen works without a Sleeper account or OpenAI key.

## Sleeper integration

Sleeper's public API is read-only; connecting a league only needs a username.
Editing a lineup uses the same private GraphQL mutation as the Sleeper web app.

```text
POST /api/integrations/sleeper/connect {username}
   -> GET /v1/user/{username}                   -> FantasyAccount (provider=sleeper)
GET  /api/integrations/sleeper/leagues?season=
   -> GET /v1/state/nfl (season)  + /v1/user/{id}/leagues/nfl/{season}
POST /api/integrations/sleeper/leagues/{league_id}/import
   -> /v1/league/{id}, /rosters, /users, /matchups/{w}, /transactions/{w}, /players/nfl
   -> mappers -> normalized DTOs -> SyncService.apply_snapshot -> DB
```

Implementation (`backend/app/providers/sleeper/`):

* `client.py` – httpx async client, retries with backoff on 429/5xx, maps
  404 / `null` bodies to `ProviderNotFound`, 429 to `ProviderRateLimited`,
  transport errors to `ProviderUnavailable`. Caches `/players/nfl` in memory
  and on disk (24h).
* `mappers.py` – pure functions from Sleeper JSON to DTOs. Notably aligns the
  ordered `starters` array with the league's `roster_positions` to derive slot
  names (`QB`, `RB`, `FLEX`…), marks `reserve`→`IR`, `taxi`→`TAXI`, rest→`BN`.
* `provider.py` – `SleeperProvider(FantasyProvider)`.
* `graphql.py` – authenticated writes. The scoring lineup is `update_matchup_leg`.
  `roster_update_starters` is intentionally unused: it can succeed, persist, and
  leave the lineup that scores unchanged.

### Editing a lineup

1. Connect Sleeper and import the league.
2. In the Sleeper web app, open DevTools → Application → Local Storage →
   `sleeper.com` → copy `token`. It is an account JWT (about a year) with full
   access to that account. Treat it like a password.
3. Paste it in **Settings**. The server checks it with `query { me { user_id username display_name } }`,
   requires it to match the connected Sleeper user, encrypts it with Fernet
   (`CREDENTIALS_KEY`, or `backend/.credentials_key` in development), and never
   returns it to the browser.
4. On **My Team**, for the current week, choose **Edit lineup** and save.

`POST /api/leagues/{id}/lineup` sends `update_matchup_leg` (week as both
`round` and `leg`, starters in slot order, empty slots as `"0"`). It then
re-reads `matchup_legs`. If that scoring lineup does not match what was sent,
the local roster is left unchanged and the API returns 409. It also re-reads
`GET /v1/league/{id}/matchups/{week}`. That public response is often cached for
a few minutes, so a successful write can still report `public_api_confirmed:
false` while `verified` is true. The app does not immediately full-sync from
the public API, because that cache would overwrite the lineup just saved.

Only the current week, only your own Sleeper roster, only eligible players, and
not IR or taxi. Demo leagues cannot be written.

Sync (`POST /api/leagues/{id}/sync`) is idempotent: leagues/teams/players/
matchups/transactions are upserted by natural keys; roster entries for a
(team, week) are replaced. `last_synced_at`, `sync_status`, `sync_error` are
tracked on the league.

Only fantasy-relevant active players plus any player referenced by a roster,
matchup or transaction are persisted (a few thousand rows, not the whole
catalogue).

## AI architecture

```text
POST /api/leagues/{id}/ai/analyze | /chat | /trade   GET /briefing
        │
        ▼
 build_tool_context()  – verifies the league belongs to the caller (404 otherwise)
        │
        ▼
 Agent.run(messages, ctx, response_model?)
   ├─ LLMClient.complete(messages, tools=registry.specs())
   ├─ for each tool_call: ToolRegistry.execute(name, args, ctx)
   │      args validated by Pydantic; handler reads only via ctx.service
   ├─ append tool results, repeat (max AI_MAX_TOOL_ROUNDS)
   └─ final: free text (chat) or JSON-schema structured output (analysis/trade),
      validated server-side with one retry on invalid JSON
```

Tools (`backend/app/ai/tools/league_tools.py`): `get_team`, `get_roster`,
`get_league_settings`, `get_current_matchup`, `get_player`, `get_player_stats`,
`get_available_players`, `search_players`, `get_recent_transactions`,
`compare_players`, `get_roster_needs`, `get_standings`, `get_recommendations`,
`get_slot_options`.

Prompts (`app/ai/prompts.py`) instruct the model to never invent statistics,
to report unavailable data as unavailable, to quote computed numbers rather
than re-deriving them, and to explain every recommendation.

`TeamAnalysis` (Pydantic) defines the "Analyze My Team" JSON: team summary,
strengths, weaknesses, lineup changes, waiver priorities, trade strategy, this
week, data gaps, confidence. The UI renders it as cards.

Recommendations (`app/domain/recommendation.py`) are typed
(`START_SIT`, `ADD_PLAYER`, `DROP_PLAYER`, `WAIVER_TARGET`, `TRADE_TARGET`,
`INJURY_ALERT`, `BYE_WEEK`, `ROSTER_WEAKNESS`) with priority, title, reason
and player ids. They are advisory; nothing ever modifies a fantasy team.

## Deterministic logic vs AI

Application code owns: roster membership, availability, slot eligibility
(`FLEX`, `SUPER_FLEX`, …), lineup legality, bye detection, injury flags, points
and projections (when a data source exists), roster limits, current matchup,
FAAB remaining, positional depth grades, start/sit swaps, waiver candidates.
See `backend/app/intelligence/`.

The LLM receives those facts through tools and produces explanations and
prioritisation. `app/ai/fallback.py` turns the same facts into templated output
when no LLM is configured.

## How to add another FantasyProvider

1. Create `backend/app/providers/<name>/` with:
   * `client.py` – auth + HTTP. For OAuth (Yahoo/NFL) store tokens on
     `FantasyAccount.encrypted_credentials` via `CredentialCipher`
     (`CREDENTIALS_KEY`). Raise `ProviderAuthError`, `ProviderNotFound`,
     `ProviderRateLimited`, `ProviderUnavailable` as appropriate.
   * `mappers.py` – pure functions producing `app.domain.provider_models` DTOs
     (`LeagueDetails`, `TeamData`, `RosterData`, `MatchupData`,
     `TransactionData`, `PlayerData`). Slot names must be normalized to the
     shared vocabulary (`QB, RB, WR, TE, FLEX, SUPER_FLEX, K, DEF, BN, IR`).
   * `provider.py` – subclass `FantasyProvider`, set `provider` and
     `capabilities`, implement the abstract methods. Override
     `fetch_league_snapshot` if a bulk endpoint exists.
2. Replace the stub in `app/providers/stubs.py` and register it in
   `ProviderRegistry.__init__`.
3. Add connect routes under `app/api/routes/integrations.py`
   (e.g. `/integrations/yahoo/oauth/start` + callback). Everything downstream
   (`IntegrationService.import_league`, `SyncService`, dashboard, AI tools) is
   provider-agnostic and needs no changes.
4. Player identity: `PlayerRepository.upsert_many(provider, players)` creates
   `player_external_ids` rows. To merge a Yahoo player with an existing Sleeper
   player, add a matching step (name+position+team) that calls
   `PlayerRepository.add_external_id(player, "yahoo", id)` before upserting.
5. Add mapper tests mirroring `tests/test_sleeper_normalization.py` with
   recorded payloads.

## API reference

Interactive docs at `/api/docs`. Summary:

```text
GET  /api/health
POST /api/auth/register | /api/auth/login        GET /api/auth/me
GET  /api/integrations/accounts | /providers
POST /api/integrations/sleeper/connect
GET  /api/integrations/sleeper/leagues?season=
POST /api/integrations/sleeper/leagues/{external_league_id}/import
PUT  /api/integrations/sleeper/token
DELETE /api/integrations/sleeper/token
POST /api/leagues/{id}/lineup
GET  /api/leagues
GET  /api/leagues/{id} | /team?week= | /matchup?week= | /players?position=&search=&available=
GET  /api/leagues/{id}/standings | /transactions | /needs | /recommendations | /briefing
POST /api/leagues/{id}/sync
POST /api/leagues/{id}/ai/analyze | /ai/chat | /ai/trade
POST /api/demo/league
GET  /api/players/{player_id}?league_id=
```

Errors are uniform: `{"error": {"code", "message", "details"}}` with proper
status codes (401/403/404/409/422/429/502/503).

## Security notes

* No fantasy-platform passwords are collected. Reading Sleeper needs only a username.
  Lineup writes use the Sleeper web-app token, stored encrypted and never returned.
* Passwords hashed with bcrypt; JWT access tokens (HS256) in the
  `Authorization: Bearer` header.
* Every `/api/leagues/{id}/...` route resolves the league through
  `leagues → fantasy_accounts → users` for the current user; foreign leagues
  return 404. AI tools receive a context built from that authorized league only.
* OpenAI and provider credentials live server-side; the browser only gets
  `NEXT_PUBLIC_API_URL`.
* Input validated by Pydantic (usernames restricted to `[A-Za-z0-9_.-]`,
  bounded list sizes, week ranges, etc.).
* `FantasyAccount.encrypted_credentials` + `CredentialCipher` (Fernet) store the
  Sleeper token. The GraphQL `me` query never selects token, email, or phone.

## Project layout

```text
fantasy_ai/
├── backend/
│   ├── alembic/                 migrations
│   ├── app/
│   │   ├── api/                 FastAPI routes + dependency wiring (deps.py)
│   │   ├── ai/                  LLM client, tools, agent loop, services, fallback
│   │   ├── core/                config, logging, security, errors
│   │   ├── db/                  base + session
│   │   ├── domain/              enums, provider DTOs, Recommendation
│   │   ├── intelligence/        deterministic engine
│   │   ├── models/              SQLAlchemy ORM
│   │   ├── nfl_data/            NFLDataProvider + local-file impl
│   │   ├── providers/           FantasyProvider ABC, registry, sleeper/, stubs
│   │   ├── repositories/        DB access
│   │   ├── schemas/             Pydantic API schemas
│   │   ├── seed/                demo league generator
│   │   └── services/            auth, integration, sync, league context, demo
│   └── tests/
├── frontend/
│   └── src/
│       ├── app/                 (auth)/login,register · (app)/dashboard,team,matchup,players,waivers,trades,assistant,settings,connect/sleeper
│       ├── components/          UI primitives + feature components
│       ├── lib/                 api client, types, auth/league contexts, queries
│       └── __tests__/
├── docs/ARCHITECTURE.md
├── docker-compose.yml
├── .env.example
└── README.md
```

## Roadmap

* Yahoo OAuth provider, ESPN (cookie/OAuth) and NFL Fantasy adapters.
* Richer NFL feeds (injuries, news) behind `NFLDataProvider`. Weekly projections already fall back to the ESPN scoreboard line when the local file has none.
* Persisted chat history, scheduled background sync, per-user rate limits.
