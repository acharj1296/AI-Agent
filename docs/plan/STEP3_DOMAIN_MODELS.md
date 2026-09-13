# STEP 3 — Core Domain Models (AI-Agent)

Status: **IMPLEMENTED** — see `docs/plan/IMPLEMENTATION_PROGRESS.md` (step 3).

## 1. Objective

Layer the full core domain model on top of the STEP 2 MongoDB repository
layer: entities, status enums, validation, specialized repositories with
pagination, an initial service layer, a typed domain-event contract (outbox),
and an audit trail — everything the agent runtime, orchestrator, task system
and workflow engine will build on.  No execution systems are implemented in
this step (no agent runtime, LLM/tool calls, task queue, workflow execution).

## 2. Architecture decision: services live in their owning modules

`docs/plan/30_FOLDER_STRUCTURE.md` keeps a modular monolith; each module owns
its data.  Services therefore live inside their modules, not in one giant
`services/` folder:

| Service | Module | Responsibility |
|---|---|---|
| `ProjectService` | `projects/services.py` | project onboarding + state (plan 13) |
| `AgentService` | `agents/services.py` | agent definition registry (plan 04/28 §2.2) |
| `TaskService` | `tasks/services.py` | task + per-attempt `TaskRun` lease records (plan 08) |
| `WorkflowService` | `workflow/services.py` | workflow definition registry + run records (plan 07) |

*(`projects/` is a new module; plan 30 lists no project module — the
orchestrator owns project state, but the orchestrator engine is a later step,
so the state-owner service lives in its own module for now.)*

`aiagent.services.build_service_layer(db)` is the composition root: it builds
the `Repositories` facade (STEP 2), the `EventPublisher`, the `AuditLogger`,
and a `ServiceLayer` dataclass with all four services.  FastAPI routes get the
layer via the new `aiagent.api.deps.ServicesDep` dependency — prepared here,
consumed by the API step.

## 3. ID, timestamps, references

- Unchanged from STEP 2: domain `id` = 32-char UUID4 hex stored as Mongo
  `_id`; `created_at`/`updated_at` are timezone-aware UTC (`tz_aware=True`).
- **New**: `db/base.py` now ships `is_doc_id()` / `validate_doc_id()` — the
  canonical shape for reference fields.  New models validate reference fields
  through it (`TaskRun.task_id`/`project_id` must be 32-char hex).
- Reference convention: reference fields ending in `*_id` that point at another
  *document* must be doc ids (UUID hex).  **Stable definition handles are
  excluded** and are documented as such: `agents.agent_id`, `models.model_id`,
  and `workflow_runs.workflow_id` (a workflow definition id, spans versions) —
  these already carry length/min-length validation.

## 4. New entities (STEP 3)

The STEP 2 MVP had `tasks` + `workflow_runs` but no per-attempt run record and
no workflow definitions.  STEP 3 adds two collections, both in `db/models.py`:

### `task_runs` — `TaskRun`
Per-attempt execution lease (docs/plan/08 §4 "worker model", lease with TTL).

| Field | Type | Notes |
|---|---|---|
| `task_id`, `project_id` | str | doc-id validated references |
| `attempt` | int | `>= 1`, default 1, unique per task |
| `status` | `TaskRunStatus` | created → queued → claimed → running → (succeeded/failed/timeout/cancelled) |
| `assigned_agent_id`, `worker_id`, `agent_run_id` | str\|None | links to agent definition / worker / concrete run |
| `lease_expires_at` | datetime\|None | future lease expiry for stale-run reclaim |
| `error_detail`, `started_at`, `completed_at` | dict/dt\|None | failure details + run timing |

### `workflows` — `Workflow`
Registered workflow definitions (docs/plan/07 §2) as versioned documents.

| Field | Type | Notes |
|---|---|---|
| `workflow_id` | str | stable definition handle (`project_build`) |
| `version` | int | `>= 1`, unique per `workflow_id` |
| `name`, `description` | str | human metadata |
| `entry`, `steps` | str / list[dict] | DAG definition consumed by the future engine |

## 5. Status enums added (`db/constants.py`)

- `TaskRunStatus`: `created`, `queued`, `claimed`, `running`, `succeeded`,
  `failed`, `timeout`, `cancelled` (worker-lease lifecycle).
- `WorkflowStatus`: `draft`, `active`, `archived` (definition lifecycle).
- `WorkflowRunStatus`: `created` **added** (record exists, engine not started)
  alongside the existing `running/paused/completed/failed/cancelled`.
  `WorkflowRun`'s default is now `created`.

## 6. Validation (Pydantic v2)

- Enum boundaries and numeric ranges enforced at the model boundary (unchanged
  STEP 2 behaviour; new models reuse it).
- Doc-id reference shape via `validate_doc_id` (`TaskRun`).
- Every repository write re-validates the merged document before persisting,
  so invalid data never reaches MongoDB (STEP 2 behaviour).
- Services add **reference-integrity checks**: creating a project requires the
  owning org to exist; creating a task requires the project; starting a task
  run requires the task; registering a workflow rejects duplicate
  `(workflow_id, version)`; creating a workflow run requires both the project
  and a registered workflow definition.

## 7. Repositories (`db/repositories.py`)

- New specialized repositories: `TaskRunRepository` (unique attempts,
  `find_by_task`, `next_attempt`) and `WorkflowRepository`
  (`find_by_id_version`, `find_active`); both wired into the `Repositories`
  facade.
- **Pagination on the generic `Repository`**: `paginate(query, *, sort, page,
  page_size)` returns a `Page[T]` (`items`, `total`, `page`, `page_size`,
  `has_next = page*page_size < total`).  Pages are 1-based, `page_size` capped
  at 200.
- Error translation unchanged: duplicate → `ConflictError` 409, connection →
  `DatabaseConnectionError` 503, other → `DatabaseError` 500 (`task_runs`,
  `workflows` labels added).

## 8. Domain events (`aiagent/events/`)

- `types.py` — **`EventType`** StrEnum with the canonical names emitted by the
  service layer (`project.created/updated`, `agent.created/updated`,
  `task.created/updated`, `task_run.started/completed/failed`,
  `workflow.registered/updated`, `workflow_run.created`) and **`DomainEvent`**,
  a forbid-extra pydantic payload (event_id, type, payload, project_id,
  emitted_by, trace_id, emitted_at, status).  `DomainEvent.build()` pulls
  `trace_id` from the request context (`aiagent/core/context.py`).
- `publisher.py` — **`EventPublisher`**: maps a `DomainEvent` to an `Event`
  document (`status: pending`) via `EventRepository`.  This **is** the outbox
  writer; a future dispatcher polls pending events.
- `audit.py` — **`AuditLogger`** + `snapshot()` helper: writes `AuditLog`
  entries (`action`/`before`/`after`/`trace_id`/resource refs); `snapshot()` is
  `model_dump(exclude_none=True)` minus the managed `id/created_at/updated_at`.

### Events emitted by services today

`project.created` (onboarding), `project.updated` (status change),
`agent.created` / `agent.updated`, `task.created`, `task_run.started`,
`task_run.completed` / `task_run.failed`, `workflow.registered`,
`workflow_run.created`.  Each mutation also writes an audit record
(before/after for updates, after-only for creates).

## 9. Indexes added (`db/indexes.py`)

| Collection | Index | Type | Reason |
|---|---|---|---|
| `task_runs` | `{task_id, attempt}` | unique | one attempt per task (serialized retries) |
| `task_runs` | `{status, created_at}` | normal | stale-lease reclaim |
| `task_runs` | `{project_id, created_at}` desc | normal | per-project run audit |
| `workflows` | `{workflow_id, version}` desc | unique | one document per (id, version) |
| `workflows` | `{status, created_at}` desc | normal | definition registry listing |

MVP collection count grows **16 → 18** (`task_runs`, `workflows`).

## 10. API preparation

`api/deps.py` exposes `ServicesDep` (`Annotated[ServiceLayer, Depends(...)]`)
so routers can inject the assembled layer and call
`services.projects.create_project(...)` etc.  No CRUD routers are added in this
step — that is the API step per the strict stop rule.

## 11. Testing

- Unit (offline, no DB): new-model validation, new enums, doc-id shape,
  event contract + context trace propagation, `Page.has_next` math.
- Integration (isolated `aiagent_test`, dropped per test): project onboarding
  (event + audit), reference-integrity `NotFoundError`s, status-change
  before/after audit, full task-run lifecycle (attempt uniqueness →
  `ConflictError`, auto attempt numbering, success/failure events), workflow
  register→run (version duplicates, unknown definition/project), agent
  register/update audit diff, real-DB pagination, outbox write with trace_id,
  audit before/after record.

## 12. Verification

| Gate | Command | Result |
|---|---|---|
| Format | `black src tests` | clean |
| Lint | `ruff check src tests` | clean (0 errors) |
| Types | `mypy src` | clean (37 files) |
| Tests | `pytest` | **69 passed** (51 unit + 18 integration incl. real MongoDB) |
| Init | `python -m aiagent.db` | 18 collections created |
| Live | `GET /healthz`, `GET /readyz` | 200, `database: ok`, timestamp, no secrets |

## 13. Decisions requiring approval

1. `task_runs` and `workflows` are new MVP collections (16 → 18), added
   before the engine steps so task/workflow systems persist against their
   domain models.
2. `WorkflowRunStatus.created` added; `WorkflowRun` default changed from
   `running` to `created`.
3. `projects/` module added (plan 30 has no project module; project-state
   service lives there until the orchestrator step).
4. Domain-event delivery is outbox-only (write `pending` to `events`); the
   dispatch/consumption mechanism is intentionally deferred.
5. Service layer covers projects, agents, tasks (+task runs), workflows;
   artifact/approval/review/message services are deferred to their system
   steps.