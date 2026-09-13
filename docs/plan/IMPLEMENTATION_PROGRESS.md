# Implementation Progress — AI-Agent

Status: **STEP 1 (Foundation) COMPLETE, STEP 2 (MongoDB primary DB) COMPLETE,**
**STEP 3 (Core Domain Models) COMPLETE, STEP 4 (Agent Registry) COMPLETE,**
**STEP 5 (Agent Runtime) COMPLETE**.
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

## Step 3 — Core domain models (DONE)

Full design: `docs/plan/STEP3_DOMAIN_MODELS.md`. STEP 3 layers the domain
model, repositories, services, typed events and audit on top of the STEP 2
MongoDB layer. No execution systems were implemented (no agent runtime, LLM,
tool, queue or workflow execution) per the stop rule.

### What was implemented

Domain model layer (`db/`):
- `db/constants.py` — new enums: `TaskRunStatus`
  (created/queued/claimed/running/succeeded/failed/timeout/cancelled),
  `WorkflowStatus` (draft/active/archived); `WorkflowRunStatus` gained
  `created` (record exists, engine not started) and `WorkflowRun` now defaults
  to it.
- `db/base.py` — `is_doc_id()` / `validate_doc_id()`: canonical 32-hex doc-id
  shape for reference fields.
- `db/models.py` — two new entity collections:
  - `task_runs` — per-attempt execution lease (docs/plan/08 §4): task_id/
    project_id (doc-id validated), attempt, status, worker/agent/agent_run
    links, lease_expires_at, error_detail, started/completed.
  - `workflows` — versioned workflow definitions (docs/plan/07): workflow_id,
    version (unique per id), name, description, entry, steps, status.
- `db/indexes.py` — MVP collections **16 → 18**; new indexes: unique
  `task_runs(task_id,attempt)`, `task_runs(status,created_at)`,
  `task_runs(project_id,created_at)`, unique `workflows(workflow_id,version)`,
  `workflows(status,created_at)`.

Repositories (`db/repositories.py`):
- New `TaskRunRepository` (attempt-unique, `find_by_task`, `next_attempt`) and
  `WorkflowRepository` (`find_by_id_version`, `find_active`), wired into
  `Repositories`.
- Generic `Repository.paginate()` → `Page[T]` (items/total/page/page_size/
  `has_next`), 1-based, page_size capped at 200.

Services (business logic on repositories; no engines):
- `projects/services.py` — `ProjectService`: onboarding `create_project`
  (org reference check), `change_status` (before/after audit), `list_projects`
  (paginated).
- `agents/services.py` — `AgentService`: `register_agent` (unique agent_id),
  `update_agent` (audit diff).
- `tasks/services.py` — `TaskService`: `create_task`, `start_task_run`
  (auto attempt numbering, unique per task), `finish_task_run`
  (status-specific events + completion timestamps).
- `workflow/services.py` — `WorkflowService`: `register_workflow`
  (versioned, unique), `list_workflows`, `create_workflow_run` (project +
  definition reference checks).
- `aiagent/services.py` — `build_service_layer(db)` composition root
  (`ServiceLayer` dataclass).

Domain events (`aiagent/events/`, module placeholders now populated):
- `types.py` — `EventType` StrEnum + `DomainEvent` (forbid-extra) contract;
  `DomainEvent.build()` pulls trace_id from request context.
- `publisher.py` — `EventPublisher` maps `DomainEvent` → `Event` doc
  (`status: pending`); this is the outbox writer (dispatch deferred).
- `audit.py` — `AuditLogger` + `snapshot()` (before/after for mutations).
- Services emit: `project.created/updated`, `agent.created/updated`,
  `task.created`, `task_run.started/completed/failed`,
  `workflow.registered`, `workflow_run.created` — each mutation also audited.

API preparation: `api/deps.py` exposes `ServicesDep` (assembled service layer)
so routers can call services; no CRUD routers added in this step.

### Setup commands used (Windows/PowerShell)

- `docker compose -f deploy/environments/local/docker-compose.yaml up -d mongodb`
  (container `aiagent-local-mongo` already healthy).
- `python -m aiagent.db` → created the two new collections (`task_runs`,
  `workflows`) + their indexes (18 MVP collections total).

### Verification results

| Gate | Command | Result |
|------|---------|--------|
| Format | `black src tests` | clean |
| Lint | `ruff check src tests` | clean (0 errors) |
| Types | `mypy src` | clean (37 files) |
| Tests | `pytest` | **69 passed** (51 unit + 18 integration incl. real MongoDB) |
| Init | `python -m aiagent.db` | 18 MVP collections + indexes created |
| Live | uvicorn + `GET /healthz`, `GET /readyz` | both 200, `ok:true`, `timestamp`, `database: ok`, no URI/credentials exposed |

Indexes verified via mongosh: `task_runs` → `uq_task_runs_task_attempt`
(unique), `ix_task_runs_status_created`, `ix_task_runs_project_created`;
`workflows` → `uq_workflows_id_version` (unique),
`ix_workflows_status_created`.

### Issues found and resolved

- Pydantic `exclude_none` omits unset optional fields from stored docs, so
  audit `before` / outbox `trace_id` are absent (not null) for create/untraced
  events; tests assert via `.get()` and set an explicit request trace to verify
  propagation.
- Initial validator for `TaskRun` reference fields used a wrong decorator body
  (broken `field="reference field"`); fixed with `ValidationInfo.field_name`.

### Decisions requiring approval

1. `task_runs` and `workflows` are new MVP collections (16 → 18), added before
   the engine steps so the task/workflow systems persist against their domain
   models.
2. `WorkflowRunStatus.created` added; `WorkflowRun` default changed from
   `running` → `created`.
3. `projects/` module added (plan 30 has no project module; the project-state
   service lives there until the orchestrator step).
4. Domain-event delivery is outbox-only (write `pending` to `events`);
   dispatch/consumption is intentionally deferred.
5. Service layer covers projects, agents, tasks (+task runs) and workflows;
   artifact/approval/review/message services deferred to their system steps.

### Remaining (later steps)

- Agent runtime (model calls, prompt engine, run state machine) — Phase 2.
- Task queue + dispatcher + DAG/cycle detection + file locks — Phase 3.
- Workflow engine: step executor, pause/resume, approval gates, watchdog —
  Phase 4.
- API routers consuming `ServicesDep` (project/task/workflow CRUD surface).
- Event dispatcher for the `pending` outbox entries.

## Step 4 — Agent registry (DONE)

Full design: `docs/plan/STEP4_AGENT_REGISTRY.md`. Formalizes the definition
registry and eligibility foundation only — no runtime, tool execution, task
assignment, queue, workflow engine, memory or automation (STEP 4 stop rule).

### What was implemented

Agent model & catalog:
- `db/models.py` — full `Agent` definition: `agent_id`, `slug`
  (lowercase-hyphenated, auto-derived when omitted), `department`/`role`/
  `capabilities`, `trusted`, `status`, semver `version`, `system_prompt_ref`,
  `owner_user_id`, created/updated timestamps, and config blocks `model`
  (`ModelConfig`), `tools` (`ToolSet`), `permissions` (`Permissions`),
  `autonomy` (`Autonomy`).
- `db/constants.py` — `AgentCapability`/`AgentRole`/`AgentDepartment` enums.
- `agents/status.py` — `assert_transition` canonical state machine:
  REGISTERED → ACTIVE/DISABLED, ACTIVE ↔ DISABLED, ACTIVE → DEPRECATED
  (terminal). INACTIVE defined but unreachable (future suspend).
- `agents/catalog.py` — `DEPARTMENT_CAPABILITIES` per department; guardrails
  `requires_trusted`, `assert_not_high_risk`; `AgentEligibilityQuery` +
  `is_eligible` (missing autonomy → level 0).
- `events/types.py` — `AGENT_ENABLED`, `AGENT_DISABLED`, `AGENT_DEPRECATED`,
  `AGENT_PERMISSIONS_CHANGED`, `AGENT_MODEL_CHANGED`, `AGENT_AUTONOMY_CHANGED`.

Service & seed:
- `agents/services.py` — `AgentRegistryService`: `register_agent`
  (STEP-3-compatible `config=` path), reads (`get_agent`/`find_agent`/
  `find_by_slug`/`find_any`/`list_agents` paginated), `update_agent`
  (auto patch-version bump on config-block changes, no downgrades, `status=`
  rejected), lifecycle (`enable_agent`/`disable_agent`/`deprecate_agent`),
  discovery (`find_by_department`/`role`/`capability`), `find_eligible`
  (query or dict), `can_use_tool`, `run_seed`. Pre-write least-privilege
  checks (`requires_trusted`); events + before/after audit on every mutation.
- `agents/seed.py` — `SYSTEM_AGENTS` (8 MVP agents, ACTIVE, trusted, v1.0.0,
  autonomy 2, `system_prompt_ref` per agent) + idempotent
  `seed_system_agents(registry)` (never overwrites); `__main__.py` →
  `python -m aiagent.agents`.
- `db/indexes.py` — agents: unique `uq_agents_agent_id`, unique `uq_agents_slug`,
  `ix_agents_status_department`, `ix_agents_status_role`,
  `ix_agents_status_capability`.

API:
- `api/routers/agents.py` — `GET /agents` (+status/department/role/capability
  filters), `GET /agents/eligible`, `GET /agents/capability/{capability}`,
  `GET /agents/{handle}` (slug then agent_id), `POST /agents`,
  `PATCH /agents/{handle}`, `POST .../enable|disable|deprecate`; request
  schemas `extra="forbid"`; `_public_agent` redaction (secrets names only);
  mounted in `api/app.py`.
- `api/errors.py` — new `PydanticValidationError` → 422 `validation_error`
  handler so domain-level validation (e.g. invalid slug) is a 4xx, not 500.

Tests:
- `tests/unit/test_agents.py` (~80 offline unit tests)
- `tests/integration/test_agent_registry.py` (23 registry tests; renamed from
  `test_agents.py` to avoid the unit test-module name collision)
- `tests/integration/test_agents_api.py` (8 HTTP tests; reachability skip +
  per-test DB reset via throwaway client to avoid the TestClient event-loop
  mismatch).

### Setup commands used (Windows/PowerShell)

- `python -m aiagent.db` → 18 MVP collections + indexes (agents indexes added).
- `python -m aiagent.agents` → seeded 8 system agents; rerun idempotent.

### Verification results

| Gate | Command | Result |
|------|---------|--------|
| Format | `black src tests` | clean (54 files) |
| Lint | `ruff check src tests` | clean (0 errors) |
| Types | `mypy src` | clean (42 files) |
| Tests | `pytest` | **152 passed** (80 unit + 45 integration + existing suites) |
| Seed | `python -m aiagent.agents` (x2) | 8 agents seeded; rerun no-op |
| Indexes | `mongosh listIndexes(agents)` | unique `agent_id`/`slug` + composites present |
| Live | uvicorn + `/healthz`, `/readyz` | 200 / `database: ok`; `GET /agents` → 8 seeded slugs |
| Secrets | src/tests/docs scan | clean |

### Issues found and resolved

- **Pydantic reserved field**: `model_config` on `Agent` collides with
  Pydantic's class attr → renamed to `model` throughout (auto-changes the STEP
  3 field name; needs approval).
- **Invalid slug → 500**: domain `ValidationError` escaped the route; added the
  `api/errors.py` handler → 422 envelope.
- **TestClient loop mismatch**: `mongo_db` fixture bound the global client to
  the pytest-asyncio loop; API tests now reachability-skip + drop the isolated
  DB per test with throwaway clients.
- **Test pollution**: reused `agent_id`s across API tests leaked into later
  assertions; per-test DB reset added.
- **Catalog typing** (`ToolSet | None`), **is_eligible autonomy** (missing →
  level 0), **mypy list invariance** (`Sequence`).

### Decisions requiring approval

1. Field renamed `model_config` → `model` (Pydantic v2 constraint).
2. INACTIVE defined but unreachable in STEP 4; suspend transition later.
3. Seed agents' `model` is `None` (profile selection deferred to model routing).
4. No `org_id` on MVP `Agent` (single-org assumption).
5. Versioning = single doc + semver + audit history.
6. Eligibility is registry-only; assignment comes with the task system.

---

## STEP 5 — Agent Runtime (DONE)

**Goal:** provider-independent model abstraction + persistent, gated `AgentRun`
execution path. **Excluded:** real tools, task/workflow engine, queue, real-model
credentials.

### Built

- `runtime/` package — `ModelProvider` protocol + frozen-dataclass
  request/response types (`models.py`), `ModelProviderRegistry`, `ModelGateway`
  (`gateway.py`), deterministic `DeterministicMockModelProvider` with scripted
  behaviors (`providers/mock.py`; env `MOCK="mock"`, `mock-default`).
- `runtime/run_state.py` — plan-37 state machine plus documented **READY →
  PAUSED** extension for approval-required runs; retry via FAILED → READY on the
  same run row (`agent_run.retrying`, `retry_count`++, attempt++); CANCELLED
  from most states; terminal PAUSED/SUCCEEDED/FAILED/CANCELLED.
- `runtime/retry.py` — `RetryPolicy`/`RetryErrorClassifier`/`compute_backoff`
  (linear `min(cap, base*2**(n-1))` + optional full jitter, seeded for tests);
  `is_retryable` = provider unavailable/timeout/rate-limit/transient.
- `runtime/context.py` gates — status/capability/tool-permission/autonomy/input
  size/execution-context; errors map to 403/404/413/422 via STEP-4 envelography.
- `runtime/prompts.py` — `FileInstructionSource` w/ traversal guard +
  system/user prompt layering; `runtime/content.py` — file-backed content store
  (`data/artifacts/runs/<id>/<kind>.txt`) + bounded inline preview +
  `output_truncated`.
- `runtime/service.py` — `AgentRuntimeService.run/find_run/find_runs_in_state`:
  resolve → config (model resolved **before** run creation so bad provider
  config never orphans a CREATED run) → gates → create READY → claim → execute
  w/ retry + cancel-aware backoff → persist outcome/events/audit.
- `AgentRun` model extension (`db/models.py`): status/state, `agent_version`,
  `workflow_run_id`, `provider`, `model`, `duration_ms`, `retry_count`,
  `correlation_id`, `input_ref/output_ref`, `input/output` previews,
  `output_truncated`, `error_code`, `started_at/completed_at` (also on FAILED);
  repository `next_attempt`/`find_agent_run`; new index
  `ix_agent_runs_agent_task_attempt`.
- Events `agent_run.created/ready/retrying/claimed/started/validating/
  succeeded/failed/paused/cancelled` + audit on transitions.
- Config `RuntimeSettings` (`core/config.py`) + `default.yaml`
  (mock, 200k/100k char caps, preview 4000, retry 3/1s base/30s cap) +
  `dev.yaml` (base 0.05s / cap 0.2s so retries are observable).
- Internal API (`api/routers/runtime.py`): `POST /internal/agents/{handle}/run`,
  `GET /internal/agent-runs/{run_id}`; mounted in `api/app.py`.
- `config/prompts/system/*/v1.md` — 8 seeded system-prompt instruction files
  exercised by live runs.

### Tests

- Unit (7 modules, ~55): run-state transition matrix, backoff math, mock script
  behaviors, gateway (timeout/empty/cancel/unknown provider typing), gates +
  context, prompt source (incl. path-traversal rejection), content stores +
  preview.
- Integration (`test_agent_runtime.py`, 20): full orchestration against real
  Mongo (events/audit persistence, attempts, metadata, denials, pause, retries,
  cancellation, config-error no-orphan). HTTP (`test_runtime_api.py`, 5): runs,
  approval pause, disabled 403, 404s using the STEP-4 reachability-skip +
  per-test reset pattern.

### Verification results

| Gate | Command | Result |
|------|---------|--------|
| Format | `black src tests` | clean |
| Lint | `ruff check src tests` | clean (0 errors) |
| Types | `mypy src` | clean (55 files) |
| Tests | `pytest` | **232 passed** (152 offline + 80 integration) |
| Live | uvicorn + POST `/internal/agents/backend-developer/run` | `decision=allowed`, `status=succeeded`, mock output, persisted run + `created,ready,claimed,started,succeeded` events + audit |
| Live | required level 3 on level-2 agent | `decision=approval_required`, `status=paused`, no model call |
| Live | disable → run → re-enable | 403 `agent_not_executable`; run succeeds again |
| Secrets | src/tests/docs scan | clean |

### Issues resolved

- Gateway wrapped typed provider errors → `except ModelError: raise` keeps
  `provider_unavailable` precise.
- Routers are mounted without `/v1`; API tests use bare `/internal/...`.
- TestClient needs `with _client() as c:` so lifespan `init_db` runs.
- `ProjectService.create_project` requires an existing org (tests seed one);
  disabled agents must be disabled via lifecycle (registry rejects DISABLED on
  create).

### Decisions requiring approval (see STEP5_AGENT_RUNTIME.md)

1. Retried runs reuse one run row (no new CREATED run per attempt).
2. Exhausted retries end FAILED (escalation deferred to human-in-loop step).
3. READY → PAUSED documented extension for approval-required runs.
4. Dataclass request/response types + provider protocol (gateway-internal).
5. Mock-only provider in STEP 5 (real providers added later).
6. File-backed content, bounded inline previews (no object storage yet).
7. Internal API carries no auth (unchanged STEP 4 posture).