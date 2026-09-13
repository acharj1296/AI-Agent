# 33 — MVP SCOPE

---

## 1. Goal

Demonstrate a **working autonomous loop**: input → planning → task decomposition →
agent assignment → development → testing → review → a deployable result.

The user can watch the system operate and approve high-risk decisions, and at the end
a greenfield CRUD web app exists.

---

## 2. Scope — In

| Capability | MVP implementation |
|---|---|
| Intake | Simple text description → project record (no UI, API only) |
| Validation | Basic feasibility check (agent output, yes/no with rationale) |
| Task decomposition | Orchestrator + PM create 10-20 concrete dev tasks (not >100) |
| Agent runtime | ModelRouter (OpenAI/Anthropic + local fallback), agent state machine |
| Agents (MVP set) | CEO, PM, System Architect, Backend Dev, Frontend Dev, Code Reviewer, QA/Test |
| Workflow | One project_build workflow (linear with approval gate at architecture) |
| Memory | Project-level memory (facts, decisions), basic task history; no org memory |
| Tools | read_file, write_file, list_dir, run_terminal, git_commit, run_tests |
| Sandbox | Docker container (Python+Node image), local FS workspace, no network |
| Task system | Full state machine + queue + dependency DAG + file-lock |
| Code review | Basic structured rubric + approve/request-changes verdicts |
| Testing | pytest + vitest (configurable per project); fix-loop (max 3) |
| Deployment | Dockerfile + compose generation; local `docker compose up`; health check |
| Observability | Structured logs + cost counter; simple metrics endpoint |
| API | REST + WebSocket (streaming task events) |
| Auth | Single API key |
| Costs | Token budget per task + project hard cap; budget warning |

---

## 3. Scope — Explicitly Out (v1+)

| Item | Reason deferred |
|---|---|
| Full security scanning (SAST + dependency audit) | Phase 8 |
| Performance testing | Phase 8 |
| Multiple environments (staging/prod) | Phase 9 |
| Monitoring agent + alerting | Phase 10 |
| Organization memory | Phase 11 |
| Learning/retrospective | Phase 11 |
| Multi-project portfolio | Phase 11 |
| Frontend dashboard | Phase 9/10 (CLI-only MVP) |
| Production cloud deployment | Phase 9 (local only) |
| High autonomy (L4/L5) | Phase 11 |
| Tool: web_search/e.g. | No research agents in MVP task flow (but capability exists) |

---

## 4. MVP Task Example (for validation)

**Input:** "Build a simple task management API with FastAPI and SQLite: users, tasks, status
updates, and basic auth."

**Expected output:** a git repo with:
- FastAPI service
- SQLite DB (SQLAlchemy models + Alembic migrations)
- Basic JWT auth
- CRUD endpoints
- pytest tests (≥80% coverage of API)
- Dockerfile
- `docker compose up` working
- README with usage instructions

---

## 5. Acceptance Criteria

| Criterion | Measure |
|---|---|
| End-to-end autonomous completion | No code written by human; only gate approvals |
| Tests pass | All generated tests pass |
| Code compiles/builds | `docker build` succeeds |
| App runs | `docker compose up` → 200 on /docs |
| Cost within budget | < $10 total (configurable) |
| Time within target | < 30 minutes (first run, optimistic) |
| Audit trail | Full trace viewable via API |

---

## 6. MVP Exit Conditions (for Phase 0+1+2+3+4+5+6+7)

1. Full task lifecycle (CREATE → COMPLETE) runs without errors.
2. Agent state machine runs without errors on a mock model.
3. Real model call (OpenAI or local Ollama) succeeds and returns code.
4. Sandbox write_file + run_terminal works.
5. Simple project_build workflow runs to completion (mocked dev steps).
6. Simple project_build workflow runs with real dev agent (API endpoint from example).
7. All unit tests pass; DB migrations up/down clean.