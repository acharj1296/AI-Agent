# 32 — DEVELOPMENT PHASES

---

## Phase 0 — Planning ✅ (this)

**Goal:** Complete planning system.
**Deliverables:** `docs/plan/` (this folder), validated across all docs.
**Exit criteria:** PLAN_INDEX, PLANNING_STATUS, and validation pass complete.

---

## Phase 1 — Core Infrastructure

**Goal:** Skeleton runnable; DB initialized; config loading; logging; secrets; basic API.
**Features:** project CRUD, config loaders, Alembic migrations, FastAPI skeleton, logging
setup, API-key auth, secrets store interface, event outbox + basic dispatcher.
**Components:** `core`, `api`, `events`, `security`, `db/migrations`.
**Dependencies:** Python, PostgreSQL, Docker.
**Tests:** unit tests on config loading, DB migrations up/down, API health endpoint.
**Exit criteria:** `docker-compose up` starts control plane + PG; API returns project CRUD;
migrations run.
**Risks:** Python async setup friction; Docker rootless configuration.

---

## Phase 2 — Agent Runtime

**Goal:** An agent can be defined in YAML and run with a model (mock or real), tool calls,
and produce structured output.
**Features:** agent definition loader, model router (one provider), prompt assembly
(memory placeholder), tool call loop, run state machine, basic token accounting.
**Components:** `agents`, `model_router`, `tools` (stub registry only).
**Tests:** unit: prompt assembly, tool guard validation; integration: mock model returns
structured output; manual: real API call (if provider key available).
**Exit criteria:** `ceo_orchestrator` agent runs on a test task with a mock model, producing
tool calls (to read_file) and completing.
**Risks:** model output format variability; tool schema matching.

---

## Phase 3 — Task System

**Goal:** Tasks can be created, queued, assigned, and completed.
**Features:** task entity CRUD, state machine, queue (in-memory), dependency DAG validation,
file-scope lock, assignment, integration with agent runtime.
**Components:** `tasks`, plus task_system's DB tables.
**Tests:** state transitions, dependency cycle detection, concurrency lock behavior.
**Exit criteria:** task READY→ASSIGNED→RUNNING→REVIEW→COMPLETED flow works end-to-end.
**Risks:** edge cases in concurrent writes.

---

## Phase 4 — Workflow Engine

**Goal:** A workflow definition executes a sequence of steps, including fan-out, gates,
pauses, retries, and approval gates.
**Features:** workflow loader, step executor (agent/gate/approval), fan-out scheduler,
resume, cancel, timeout, approval integration.
**Components:** `workflow`, plus `approval` service.
**Tests:** a 6-step workflow runs to completion; a workflow with approval gate pauses and
resumes after manual decision; a workflow with timeout fails gracefully.
**Exit criteria:** a simple research-only workflow runs non-interactively with mocked model.
**Risks:** pause/resume idempotency.

---

## Phase 5 — Memory

**Goal:** Memory persists across runs; context injected per run; vector search works.
**Features:** memory CRUD for project/task layers, embedding + vector search (pgvector),
short-term episode storage + distillation, context budget assembly, org memory basics.
**Components:** `memory`.
**Tests:** embedding round-trip, semantic search relevance (smoke), context budget cap.
**Exit criteria:** agent run receives memory context; task completion writes memory; top-3
semantic hits returned for a sample query.
**Risks:** embedding quality; vector index performance.

---

## Phase 6 — Tool System + Sandbox

**Goal:** Real tools execute inside a sandboxed container; permission guard enforced.
**Features:** sandbox container lifecycle (warm pool), gatekeeper, file tools (read/write),
git tool (commit/push), run_terminal (guarded), web_search (allow-listed egress proxy),
run_tests (pytest wrapper), permission guard integration.
**Components:** `sandbox`, `tools` (full implementations).
**Tests:** write_file + read_file round-trip; run_terminal executes "echo hello" safely;
blocked command denied; network blocked in default mode.
**Exit criteria:** a dev agent writes code in a sandbox container; test agent runs pytest and
returns results.
**Risks:** Docker socket access; rootless mode limitations.

---

## Phase 7 — Autonomous Development

**Goal:** An orchestrator can take a simple user-story-level task, assign it to a dev agent,
who implements code in a repo within the sandbox, writes tests, and submits for review.
**Features:** project repo init, workspace injection to sandbox, full dev workflow (plan →
code → test → commit), code review agent (basic rules), artifact recording.
**Components:** `orchestrator`, `tasks`, `agents`, `sandbox`, `artifacts`.
**Tests:** e2e: simple API endpoint implemented from description, tests pass, diff reviewed.
**Exit criteria:** on a greenfield "create a FastAPI hello-world with test" task, the system
produces working code and tests.
**Risks:** model quality on actual code; code style consistency; repo state management.

---

## Phase 8 — QA & Security

**Goal:** Automated test pipeline; security scanning; bug-fix loop.
**Features:** test layer configuration per project, full test suite runner, SAST scan
(bandit/semgrep), dependency audit, bug triage + fix loop, coverage tracking.
**Components:** `qa`, `security`, `testing` (scheduler), `tasks` (fix loop).
**Tests:** fix-loop terminates within 3 retries on a deliberate bug; security scan
flags a finding and creates fix task.
**Exit criteria:** a project with a deliberate bug is automatically detected and fixed
by the system without human input.
**Risks:** false positives in security scans; noisy test failures.

---

## Phase 9 — Deployment

**Goal:** System can deploy a user project locally (Docker Compose) with rollback.
**Features:** Dockerfile generator for user project, compose file, deploy to local env,
health check, rollback on failure, deploy record, basic monitoring config generator.
**Components:** `deployments`, `devops` tools.
**Tests:** deploy a hello-world app; health check green; introduce failure → rollback.
**Exit criteria:** end-to-end from code merge to running service on localhost.
**Risks:** user project Dockerfile generation quality.

---

## Phase 10 — Monitoring

**Goal:** Platform observability dashboard; incident handling; post-deploy health loop.
**Features:** metrics collection, event dashboard API, cost dashboard, alerting (basic),
incident lifecycle, post-deploy monitoring loop (devops_monitor).
**Components:** `monitoring`, `api` (metrics endpoints).
**Tests:** alert triggers on budget exceed; incident created on deploy health failure.
**Exit criteria:** a full dashboard query returns project health + cost summary.
**Risks:** metric cardinality; log volume.

---

## Phase 11 — Advanced Autonomy

**Goal:** Full project build from intake → deployed app with human approval gates only.
**Features:** full project_build workflow (intake → research → PRD → arch → dev → test →
deploy), retrospective learning, org memory accumulation, cost optimization, multi-project
portfolio support.
**Tests:** complete greenfield project (e.g., blog platform) builds and deploys.
**Exit criteria:** a non-trivial app builds end-to-end with no code edits by human.
**Risks:** compounding errors in long workflows; agent prompt quality drift.