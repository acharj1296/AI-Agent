# STEP 4 — Agent Registry (DONE)

Formalizes the definition registry and eligibility foundation for agents. No
runtime, no tool execution, no task assignment, no queue, no workflow engine,
no memory and no automation were implemented (STEP 4 stop rule).

## Scope

1. Full `Agent` definition model: identity, slug, roles/departments,
   capabilities, status state machine, config blocks (`model`, `tools`,
   `permissions`, `autonomy`), `model_config` → renamed **`model`** (see
   Issues), least-privilege guardrails.
2. `AgentRegistryService` — register / get / update / lifecycle transitions /
   discovery / eligibility / seed. Backward compatible with the STEP-3
   `register_agent(agent_id, department, name, config=...)` and
   `update_agent(..., config=...)` signatures.
3. Canonical capability catalog `agents/catalog.py`.
4. Idempotent 8-agent system seed (`agents/seed.py` + `python -m aiagent.agents`).
5. Mongo indexes, events, audit, minimal secure FlatPath `agents` API.

## Agent model (STEP 4 shape)

Identity & classification:
- `agent_id` (unique), `slug` (unique, lowercase-hyphenated via validator;
  auto-derived from `agent_id` when omitted), `name`, `description`,
  `department` (`AgentDepartment`), `role` (`AgentRole`), `capabilities`
  (subset of `AgentCapability`), `owner_user_id` (optional), `org_id` (not on
  the MVP Agent — single-org decision from STEP 2/3).
- `trusted: bool` — default False; gating registration/updates of high-risk or
  admin-scoped tool sets.
- `status` via `agents/status.py` — one canonical transition machine:
  REGISTERED → ACTIVE, DISABLED; ACTIVE ↔ DISABLED; ACTIVE → DEPRECATED,
  DEPRECATED → DEPRECATED is terminal. INACTIVE exists as a status value but is
  not reachable through the service in STEP 4 (future suspend transition) —
  `update_agent(status=...)` is rejected with `InvalidStateError`, and
  `register_agent` accepts only REGISTERED | ACTIVE.
- `version: Version` (semver) — explicit version must not downgrade
  (`_validated_version`); `update_agent` auto-bumps the patch when any config
  block (`model`/`tools`/`permissions`/`autonomy`/`config`) changes
  (`_bump`).
- `system_prompt_ref: str | None` — prompt-store reference (prompt system is a
  later step); seed agents point at `system/<agent_id>/v1`.
- `created_at` / `updated_at`.

Config blocks (`db/models.py` submodels):
- `model: ModelConfig | None` — provider/profile/params; seeded agents keep
  `None` (generic profile chosen later with the model-routing step).
- `tools: ToolSet | None` — build/test/review file scopes + shell/network
  flags; flat repo-safe permissions only in STEP 4.
- `permissions: Permissions | None` — `filesystem`, `tool_groups`,
  `secrets` (names only, never values), `network`.
- `autonomy: Autonomy | None` — `level` (0–5) + defaults. Missing autonomy is
  treated as level 0 in `is_eligible`.

## Capability catalog (`agents/catalog.py`)

- `DEPARTMENT_CAPABILITIES` — canonical capability set per department
  (`development`, `quality`, `product`, `architecture`, `security`,
  `operations`, `orchestration`).
- `AgentCapability` / `AgentRole` / `AgentDepartment` enums (`db/constants.py`).
- Guardrails: `requires_trusted(agent)` (admin tool scopes / shell / network
  / code execution / secrets) and `assert_not_high_risk(agent)`; both run
  pre-write so a non-trusted or high-risk definition change → `PolicyViolationError`.
- `AgentEligibilityQuery` (forbid-extra) — `required_capabilities`,
  `departments`, `roles`, `required_tool_ids`, `requires_write_filesystem`,
  `requires_code_execution`, `requires_network`, `min_autonomy_level`
  (0 ≤ l ≤ 5, default 0), `status` (default ACTIVE).
- `is_eligible(agent, query)` — registry-level matching only (actual task
  assignment is a later step).

## Status state machine (`agents/status.py`)

`assert_transition(current, target)` enforces the canonical edge set; invalid
transitions raise `InvalidStateError` (409). Lifecycle mutation service methods
(`enable_agent`/`disable_agent`/`deprecate_agent`) use it and emit the matching
event (`AGENT_ENABLED`/`AGENT_DISABLED`/`AGENT_DEPRECATED`).

## AgentRegistryService (`agents/services.py`)

- `register_agent(agent_id, department, name, *, slug=None, description=None,
  role=None, capabilities=(), status=None, trusted=False, config=None,
  model=None, tools=None, permissions=None, autonomy=None, version=None,
  system_prompt_ref=None, owner_user_id=None)` — duplicate `agent_id`/`slug` →
  `ConflictError` **before** building the model; least-privilege policy check;
  emits `AGENT_CREATED`, audits `agent.register`.
- Reads: `get_agent(doc_id)` → `Agent | None`; `find_agent(agent_id)`;
  `find_by_slug(slug)`; `find_any(slug, agent_id)` (seed/lookup helper — slug
  wins, then agent_id); `list_agents(status=/department=/role=/capability=,
  page, page_size)` → paginated `Page[Agent]`.
- Updates: `update_agent(agent_id, *, status=None(rejected), **fields)` —
  config-block handling, auto version bump, pre-write policy validation,
  emits `AGENT_UPDATED` + aspect events (`AGENT_PERMISSIONS_CHANGED`,
  `AGENT_MODEL_CHANGED`, `AGENT_AUTONOMY_CHANGED`), audits before/after.
- Discovery: `find_by_department`, `find_by_role`, `find_by_capability`;
  `find_eligible(query)` (query or dict, candidate narrowing, then
  `is_eligible`).
- `can_use_tool(agent, tool_id)` — tool-scope check against the catalog.
- `run_seed()` → `agents/seed.seed_system_agents(self)` (idempotent).

### Seed (`agents/seed.py`, `agents/__main__.py`)

`SYSTEM_AGENTS` — 8 MVP agents, all ACTIVE, trusted=True, v1.0.0, autonomy
level 2, `system_prompt_ref` set, tools/permissions per the 36 matrix:

| slug            | agent_id          | department   | role          |
|-----------------|-------------------|--------------|---------------|
| orchestrator    | `ceo_orchestrator`   | orchestration | orchestrator |
| product-manager | `pm_product_manager` | product      | product-manager |
| system-architect| `arch_system`        | architecture | system-architect |
| backend-developer | `dev_backend`      | development  | backend-developer |
| frontend-developer| `dev_frontend`     | development  | frontend-developer |
| code-reviewer   | `qa_code_reviewer`   | quality      | code-reviewer |
| qa-lead         | `qa_lead`            | quality      | qa-lead       |
| test-automation | `qa_test_automation` | quality      | test-automation |

`seed_system_agents(registry)` skips agents that already exist (by slug or
agent_id) and never overwrites; reruns are no-ops. CLI: `python -m aiagent.agents`.

## Events & audit

New `EventType` values: `AGENT_ENABLED`, `AGENT_DISABLED`, `AGENT_DEPRECATED`,
`AGENT_PERMISSIONS_CHANGED`, `AGENT_MODEL_CHANGED`, `AGENT_AUTONOMY_CHANGED`
(added to the STEP 3 `AGENT_CREATED` / `AGENT_UPDATED`). Every mutation writes
a typed `pending` event to `events` and a before/after row to `audit_logs`
(dispatch deferred to the events step).

## Mongo indexes (agents)

| Index                      | Unique | Purpose                          |
|----------------------------|:------:|----------------------------------|
| `uq_agents_agent_id`       | yes    | natural identity                 |
| `uq_agents_slug`           | yes    | lookup + auto-slug conflict       |
| `ix_agents_status_department` | no  | list-by-status+department        |
| `ix_agents_status_role`    | no     | list-by-status+role              |
| `ix_agents_status_capability`| no   | capability lookups/eligibility   |

## API (`api/routers/agents.py`, mounted in `api/app.py`)

All responses use the envelope (`ok`/`data`/`meta`/`trace_id`); errors use the
`error` envelope. Requests are `extra="forbid"` and slugs/bodies validated
(domain `pydantic.ValidationError` → 422 via the new handler in
`api/errors.py`).

| Method | Path                          | Description                                    |
|--------|-------------------------------|------------------------------------------------|
| GET    | `/agents`                     | List (status/department/role/capability + page)|
| GET    | `/agents/eligible`            | Registry-level eligibility                     |
| GET    | `/agents/capability/{capability}` | Agents carrying a capability                |
| GET    | `/agents/{handle}`            | By slug, then agent_id (or 404 envelope)       |
| POST   | `/agents`                     | Register (201)                                 |
| PATCH  | `/agents/{handle}`            | Partial update (status rejected → 422)         |
| POST   | `/agents/{handle}/enable`     | Transition to ACTIVE                           |
| POST   | `/agents/{handle}/disable`    | Transition to DISABLED                         |
| POST   | `/agents/{handle}/deprecate`  | Terminal transition                            |

`_public_agent` redaction: the API never exposes secret values —
`permissions.secrets` names only; prohibited key names asserted in tests.

## Tests

- `tests/unit/test_agents.py` (~80 offline tests): model validation, slug,
  semver `_validated_version`/`_bump`, tool permissions, capabilities, config
  submodels, status transitions, least-privilege guardrails, eligibility
  (dict/object), version helpers.
- `tests/integration/test_agent_registry.py` (23): register/persist, duplicate
  `agent_id`, default slug, lookups, update + auto version bump + audit +
  aspect events, status kwarg rejection, downgrade rejection, slug collision,
  high-risk update denial, lifecycle transitions, discovery, list filters,
  eligibility, `can_use_tool`, least-privilege denial, trusted registration,
  seed idempotency (8 agents, no dupes on rerun).
- `tests/integration/test_agents_api.py` (8, exercise the real FastAPI app):
  list/create roundtrip, duplicate → 409 envelope, invalid slug → 422,
  unknown → 404 envelope, update + lifecycle + version bump, `status` field in
  PATCH → 422, eligible + capability endpoints, public payload never leaks
  secret material.

## Verification results (2026-09-13)

| Gate | Command | Result |
|------|---------|--------|
| Format | `black src tests` | clean (54 files) |
| Lint | `ruff check src tests` | clean (0 errors) |
| Types | `mypy src` | clean (42 files) |
| Tests | `pytest` | **152 passed** (unit + integration incl. real MongoDB) |
| Init | `python -m aiagent.db` | 18 collections initialized |
| Seed | `python -m aiagent.agents` (x2) | seeded 8 system agents; rerun idempotent |
| Indexes | `mongosh listIndexes(agents)` | `uq_agents_agent_id`, `uq_agents_slug` (unique), status-composite indexes present |
| Live | uvicorn + `/healthz`, `/readyz` | both 200, `database: ok`; `GET /agents` → 8 seeded slugs |
| Secrets | scan of src/tests/docs | no keys/tokens/secrets matched |

## Issues found and resolved

1. **Pydantic reserved field**: a field named `model_config` on `Agent`
   collides with Pydantic's own class attr (mypy internal error "too many class
   plugin hook passes"). Renamed to **`model`** everywhere (model, service
   params, router schemas, `_public_agent`, seed).
2. **Unhandled domain validation → 500**: an invalid slug raised
   `pydantic.ValidationError` inside the route and hit the generic handler,
   returning 500 instead of 422. Added a `PydanticValidationError` handler in
   `api/errors.py` mapping to the 422 `validation_error` envelope.
3. **TestClient event-loop mismatch**: the old `mongo_db` fixture binds the
   global Motor client to the pytest-asyncio loop while `TestClient` runs its
   own portal loop (`Task ... attached to a different loop`). API tests now
   reachability-skip via a throwaway client and reset the isolated
   `aiagent_test` DB per test with a fresh client.
4. **Isolation**: `agent_id` reuse across earlier API tests polluted later ones
   (409s and a polluted eligibility result); DB is now dropped before every
   test.
5. **Catalog typing**: `_tool_set_is_admin` annotation fixed to
   `ToolSet | None`.
6. **Eligibility**: missing autonomy previously required a non-None value;
   treated as level 0 instead.
7. **mypy list invariance**: `capabilities`/query lists use `Sequence[...]`.

## Decisions requiring approval

1. The config block field is named `model` (not `model_config`) — a deliberate
   deviation required by Pydantic v2 (see Issue 1).
2. INACTIVE is defined but unreachable in STEP 4; a suspend transition is a
   later step.
3. `model` for the 8 seeded system agents is `None` (generic model profile
   deferred to the model-routing step).
4. `org_id` is not on the MVP `Agent` (single-org assumption).
5. Versioning = single document + semver + audit-trail history (no separate
   versioned docs) — consistent with STEP 3 workflows.
6. Eligibility matches the registry only; task assignment/planning is later.

## Remaining (later steps)

- Agent runtime: prompt engine, model calls, run state machine — Phase 2.
- Tool execution/sandboxing; secret-store lookup of named secrets.
- Task queue + dispatcher + assignment via `find_eligible` — Phase 3.
- Workflow engine, events dispatcher (drains `events` outbox).
- Per-agent model profile selection when model routing lands.