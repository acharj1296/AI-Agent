# MongoDB Design — AI-Agent (STEP 2)

Status: **IMPLEMENTED** — see `docs/plan/IMPLEMENTATION_PROGRESS.md` (step 2).

## 1. Decision: MongoDB is the primary database

This step replaces the STEP-1 PostgreSQL/SQLAlchemy layer with MongoDB as the
**primary** database, per a user decision that overrides the original planning
lock on PostgreSQL (`docs/plan/28_database_design.md`) and the tech stack
(`docs/plan/31_technology_stack.md`). PostgreSQL files were removed from the
repo (the docker-compose Postgres service, Alembic, `db/versions/*`, and the
STEP-1 ORM models).

- Driver: **Motor** (async) + **PyMongo** + the existing **Pydantic v2**
  validation framework. The backend is Python/FastAPI; the "TypeScript
  architecture" references in the STEP-2 brief therefore map to the Python
  equivalents (`motor` instead of `mongodb` TS driver, Pydantic models instead
  of TS interfaces).
- Vector search backing store is now **open**: choose Atlas Vector Search or a
  manual embedding index later. Not part of this step.

## 2. Layering

```
Application (FastAPI routers)
        │  uses
Service layer (future steps - business logic lives here)
        │  uses
Repository layer  (db/repositories.py - data access ONLY, no business logic)
        │  reads/writes
MongoDB collections
```

Repositories never leak raw driver errors: MongoDB exceptions are translated in
`db/repositories._translate()` to safe application errors
(`ConflictError` 409 for duplicate keys, `DatabaseConnectionError` 503 for
connection/timeout failures, `DatabaseError` 500 otherwise).

## 3. ID and timestamp policy

- Domain `id` is a **UUID4 hex string (32 chars)** stored as the Mongo `_id`
  (mapped by `BaseDocument.to_doc()` / `from_doc()` in `db/base.py`).
- `created_at` / `updated_at` are timezone-aware UTC datetimes; the Motor client
  is created with `tz_aware=True` so BSON dates round-trip as aware UTC.
- Enums are validated at the Pydantic boundary; invalid values never reach the
  database.

## 4. Collections

### MVP (16, implemented)

> **STEP 3 addendum (2026-09-13):** `task_runs` (per-attempt task execution
> leases) and `workflows` (versioned workflow definitions) were added as
> **new** MVP collections — the MVP collection count is now **18**. Full layout
> in `docs/plan/STEP3_DOMAIN_MODELS.md`. The table below lists the original 16;
> the two additions are documented in that STEP 3 design doc.

| Collection | Purpose |
|---|---|
| `organizations` | company/namespace root; contains budgets + autonomy defaults |
| `users` | human users (email unique, lower-cased) |
| `projects` | project state (stage, status, autonomy level, decisions, facts) |
| `agents` | agent registry (per-org agents with role/model/persona) |
| `agent_runs` | one execution attempt of an agent |
| `tasks` | typed subtasks with priority/status/dependencies |
| `workflow_runs` | workflow execution instances |
| `artifacts` | immutable, versioned outputs (source, plan, review, report, docs) |
| `messages` | conversation channel + outbox-style delivery poll |
| `memories` | long-term context rows (auto/declared), future embedding field |
| `approvals` | human approval gate records (3-tier) |
| `reviews` | code/test/policy review verdicts per task |
| `tool_calls` | tool execution audit (status, input/output refs, duration) |
| `models` | model registry (provider unique `model_id`, cost/latency caps) |
| `events` | domain events (outbox pattern source) |
| `audit_logs` | immutable actor/action audit trail |

### Deferred to later phases (6)

`providers`, `knowledge`, `deployments`, `environments`, `incidents`,
`test_runs` — modeled in `docs/plan/28` but not created in STEP 2 to keep the
active surface small. Init creates the 16 MVP collections only; the init script
and init-time assertions are written so deferred collections are **not** created.

## 5. Indexes

Defined in `db/indexes.py`. Every index serves a documented query pattern (the
`reason` field records why it exists); there are no speculative indexes.
Highlights:

- Unique: `users.email`, `agents.agent_id`, `models.model_id`,
  `artifacts(project_id, name, version)`.
- Hot reads: org project lists (`org_id,status`), task boards (`project_id,
  status`), worker pull order (`status,priority,created_at`), approval queue
  (`status,created_at`), event outbox (`status,created_at`).

## 6. Initialization and lifecycle

- `python -m aiagent.db` (or `scripts/migrate.ps1` / `make migrate`) → connect,
  ping (fail-fast → `DatabaseConnectionError`), ensure collections + indexes.
- The FastAPI lifespan (`api/app.py`) awaits `init_db(settings)` on startup and
  `close_db()` on shutdown; startup fails clearly if MongoDB is unreachable.
- `/readyz` reports `database: ok` only after a real `ping`; neither health
  endpoint exposes the URI or credentials.

## 7. Configuration & security

- Settings: `config/default.yaml` + `config/env/<env>.yaml` + env overrides
  (`MONGODB_URI`, `MONGODB_DATABASE`, `MONGODB_SERVER_SELECTION_TIMEOUT_MS`,
  `MONGODB_CONNECT_TIMEOUT_MS`, `MONGODB_MAX_POOL_SIZE`, `MONGODB_MIN_POOL_SIZE`).
- No real credentials in git: `.env.example` carries placeholders only; the
  dev URI points at the local compose container (port 27018, which avoids a
  conflict with a system MongoDB service on 27017).
- `db/client.redact_uri()` strips credentials from any logged URI.

## 8. Local development

```powershell
docker compose -f deploy/environments/local/docker-compose.yaml up -d mongodb
.\scripts\migrate.ps1          # python -m aiagent.db
uvicorn aiagent.api.app:app --reload
```

Integration tests run against the isolated `aiagent_test` database (dropped
after each test) and skip automatically when MongoDB is unreachable.