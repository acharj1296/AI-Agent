# Implementation Progress — AI-Agent

Status: **STEP 1 (Foundation) COMPLETE, STEP 2 (MongoDB primary DB) COMPLETE**.
Last updated: 2026-09-13

## Step 1 — Foundation (DONE)

What was implemented and verified for STEP 1, aligned with `docs/plan/29_api_envelope.md`,
`docs/plan/31_technology_stack.md`, `docs/plan/32_implementation_phases.md`, and `docs/plan/49_checklist.md`.

### Files created

Root / config:
- `pyproject.toml` — package metadata + pinned dependency ranges + Ruff/Black/mypy/pytest config
- `.gitignore`, `.env.example`
- `README.md` (rewritten; was boilerplate UTF-16LE stub)
- `Makefile` (Unix convenience; Windows uses `scripts/*.ps1`)
- `config/default.yaml`, `config/env/dev.yaml`, `config/env/staging.yaml`, `config/env/prod.yaml`

Source (`src/aiagent/`):
- `__init__.py`, `version.py`
- `core/config.py` — layered YAML + env-var config (default → env/<APP_ENV> → env vars), `extra="forbid"`
- `core/context.py` — request-context ids (`request_id` / `trace_id` via contextvars)
- `core/errors.py` — `AiAgentError` hierarchy with HTTP status + error code
- `core/logging.py` — JSON log formatter + `setup_logging()`
- `db/base.py`, `db/models.py` (*organizations*, *users* per plan 28 §2.12), `db/session.py` (async engine, `ping()`)
- `api/app.py` — FastAPI app factory + lifespan + request-context middleware + exception handlers
- `api/deps.py`, `api/envelope.py` (success/error envelope + trace_id), `api/errors.py`
- `api/routers/health.py` — `GET /healthz`, `GET /readyz`
- Placeholder `.gitkeep` dirs for all future modules (agents, workflows, tasks, orchestrator, model_router,
  memory, knowledge, tools, sandbox, artifacts, approval, events, monitoring, security, deployments, cli)

Database / ops:
- `db/alembic.ini`, `db/env.py` (async env, dynamic URL from settings), `db/script.py.mako`
- `db/versions/0001_identity.py` — creates `organizations` + `users` (FK `org_id` NOT NULL, `ON DELETE CASCADE`)
- `deploy/environments/local/docker-compose.yaml` — Postgres 16 (+pgvector, used later)
- `scripts/bootstrap.ps1`, `scripts/bootstrap.sh`, `scripts/migrate.ps1`, `scripts/run.ps1`

Tests:
- `tests/conftest.py` (settings-cache reset, engine teardown)
- `tests/unit/test_config.py` (8), `tests/unit/test_core.py` (9), `tests/unit/test_health.py` (7)
- `tests/integration/test_db.py` (4, auto-skip when Postgres unreachable; DB state cleaned per test)

### Setup commands used (Windows/PowerShell)

- `uv venv --python 3.12 .venv`
- `uv pip install --python .venv/Scripts/python.exe -e ".[dev]"`
- Docker Desktop started; `docker compose -f deploy/environments/local/docker-compose.yaml up -d db`
  → container `aiagent-local-db` healthy, engine Server Version 29.7.2
- `alembic -c db/alembic.ini upgrade head` → applied `0001_identity`

### Verification results

| Gate | Command | Result |
|------|---------|--------|
| Format | `black src tests db` | clean |
| Lint | `ruff check src tests db` | clean (0 errors) |
| Types | `mypy src` | clean (18 files) |
| Tests | `pytest` | **28 passed** (24 unit + 4 integration incl. real-DB) |
| Live | uvicorn + `GET /healthz`, `/readyz`, `/` | 200, `ok:true`, `trace_id` present; `/readyz` → `database: ok` |

### Remaining Phase-1 work (not in STEP 1 scope)

- Project CRUD API (`/v1/projects`) + per-project config
- API-key auth middleware + API-key tables/hashing
- Secret store (encrypted storage for model/tool secrets)
- Event outbox pattern (persistent event queue)
- Docker Compose control-plane service wiring (modular monolith packaging)
- Sandbox image/build tooling
- Populating `config/agents`, `config/workflows`, `config/models`, `prompts/`, `knowledge/`
- End-to-end tests + fixtures (`tests/e2e`, `tests/test_fixtures`)

## Step 2 — MongoDB primary database (DONE)

Full design: `docs/plan/MONGODB_DESIGN.md`. **Decision change (needs approval):
the user chose MongoDB as the PRIMARY database, overriding the planning lock on
PostgreSQL** from `docs/plan/28_database_design.md` and `31_technology_stack.md`.
The STEP-2 brief referenced a "TypeScript architecture", but this repo is
Python 3.12 / FastAPI, so MongoDB is integrated with the Python equivalents
(Motor async driver + PyMongo + Pydantic v2 validation). The vector-search
backing store is now open (Atlas Vector Search or manual embeddings) - not
solved in this step.

### What was implemented

Database layer (replaces the STEP-1 SQLAlchemy/PostgreSQL/Alembic stack):
- `db/constants.py` — enumerated domain enums (`ProjectStage/Status`,
  `TaskPriority/Status`, `AgentRunStatus`, `WorkflowRunStatus`, `ApprovalTier/
  Status`, `ArtifactStatus`, `MessageType/Status`, `ReviewVerdict`,
  `ToolCallStatus`, `ModelProvider`, `MemoryKind`, `EventStatus`, `UserRole`).
- `db/base.py` — Pydantic `BaseDocument` (`id` UUID hex as Mongo `_id`,
  authored timestamps, `to_doc()`/`from_doc()` mapping).
- `db/models.py` — 16 MVP document models (organizations, users, projects,
  agents, agent_runs, tasks, workflow_runs, artifacts, messages, memories,
  approvals, reviews, tool_calls, models, events, audit_logs). Deferred:
  providers, knowledge, deployments, environments, incidents, test_runs.
- `db/client.py` — Motor client factory (+ping/close, `tz_aware=True`,
  `redact_uri()` to strip credentials from logs).
- `db/indexes.py` — every index documented with a reason; unique on
  `users.email`, `agents.agent_id`, `models.model_id`,
  `artifacts(project_id,name,version)`; `ensure_collections_and_indexes`.
- `db/repositories.py` — generic `Repository[T]` + repository per entity +
  `Repositories` facade; data access only (no business logic); every write
  re-validates through the Pydantic model; driver errors translated to
  `ConflictError`(409)/`DatabaseConnectionError`(503)/`DatabaseError`(500).
- `db/session.py` + `db/init.py` + `db/__main__.py` — async lifecycle
  (`init_db` connects→pings fail-fast→ensures collections+indexes; `close_db`;
  `ping`), CLI entry `python -m aiagent.db`.

Wiring / app:
- `core/config.py` — `DBSettings` becomes MongoDB settings (uri, name, timeouts,
  pool sizes) with `MONGODB_*` env overrides.
- `api/app.py` lifespan awaits `init_db(resolved)`, fail-fast on `AiAgentError`;
  `api/deps.py` `DbDep` yields `AsyncIOMotorDatabase`; `api/routers/health.py`
  adds `timestamp` to `/healthz` + `/readyz` (no URI/credentials ever).
- Config: `config/default.yaml`, `config/env/{dev,staging,prod}.yaml`,
  `.env.example` → MongoDB settings (dev URI uses port 27018 to avoid a
  conflict with a system MongoDB Service on 27017).
- Ops: docker-compose `mongodb` service (`mongo:8`, auth `aiagent/aiagent`,
  healthcheck via mongosh, `./mongo-init` first-boot collections, named volume);
  `migrate.ps1`/`Makefile migrate` → `python -m aiagent.db`; `run.ps1` starts
  the mongodb service.
- Removed: Postgres compose service, `db/alembic.ini`, `db/env.py`,
  `db/script.py.mako`, `db/versions/*`, SQLAlchemy/asyncpg/alembic deps.

Tests:
- `tests/conftest.py` — resets settings cache + closes the global client; an
  autouse `_offline_database` fixture stubs `aiagent.api.app.init_db` so unit
  tests never need MongoDB (skipped for `integration`-marked tests).
- `tests/unit/test_config.py` — MongoDB config assertions (MONGODB_URI/AIAGENT
  env overrides); new `tests/unit/test_db_documents.py` — document validation,
  `_id` mapping, enums/email constraints, error translation (`DuplicateKeyError`
  → `ConflictError`, other failures → `DatabaseError`); `test_health.py` asserts
  the new `timestamp` field.
- `tests/integration/test_db.py` — uses the isolated `aiagent_test` db (dropped
  per test), skips when MongoDB unreachable; covers ping, collections created
  (and deferred ones NOT created), index uniqueness flags, repository
  round-trip + duplicate → `ConflictError`, validation via repository,
  missing-id returns `None`, `init_db` fail-fast on unreachable port, and a
  readiness check against real MongoDB (via `httpx.ASGITransport` so requests
  run on the pytest-asyncio loop the Motor client is bound to).

### Setup commands used (Windows/PowerShell)

- `uv venv --python 3.12 .venv`; `uv pip install --python .venv/Scripts/python.exe -e ".[dev]"`
  (+ uninstalled stale `sqlalchemy asyncpg alembic`).
- `docker compose -f deploy/environments/local/docker-compose.yaml up -d mongodb`
  → container `aiagent-local-mongo` healthy.
- `python -m aiagent.db` → created the 16 MVP collections + indexes.
- `docker rm -f aiagent-local-db` — removed the STEP-1 Postgres container.

### Verification results

| Gate | Command | Result |
|------|---------|--------|
| Format | `black src tests` | clean |
| Lint | `ruff check src tests` | clean (0 errors) |
| Types | `mypy src` | clean (24 files) |
| Tests | `pytest` | **44 passed** (36 unit + 8 integration incl. real MongoDB) |
| Live | uvicorn + `GET /healthz`, `GET /readyz` | both 200, `ok:true`, `timestamp` present, `database: ok`, no URI/credentials exposed |
| Indexes | `mongosh listIndexes` (users/models/artifacts/events/tasks) | unique flags + documented indexes present |

### Issues found and resolved

- **Windows port conflict**: a system MongoDB service was bound to
  `127.0.0.1:27017`, shadowing the Docker Mongo and making Python auth fail.
  Fixed by publishing the container on **27018** (user-approved).
- **Motor event-loop mismatch**: creating the Motor client inside `asyncio.run()`
  in the fixture broke cross-loop usage with pytest-asyncio. Fixed by making the
  fixture async (same loop as the test) and using `httpx.ASGITransport` for the
  readiness test instead of `TestClient`'s separate loop.
- **BSON datetimes**: naive datetimes on round-trip; fixed with `tz_aware=True`.
- **Env leak**: the fixture mutated `MONGODB_DATABASE` globally; removed.

### Decisions requiring approval

1. MongoDB replaces PostgreSQL as the primary DB (overrides plan 28/31).
2. MongoDB is integrated with Python equivalents (Motor/Pymongo/Pydantic), not
   the TypeScript drivers the STEP-2 brief referenced.
3. Deferred collections (providers, knowledge, deployments, environments,
   incidents, test_runs) are not created in STEP 2.
4. Vector-search backing store (Atlas/search provider) is unresolved.