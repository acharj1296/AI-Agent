# 49 — IMPLEMENTATION CHECKLIST

Actionable checklist for the implementing team (phases aligned with `32`. Verify each row
has a task, owner, and test.

---

## Phase 0 — Planning (DONE)
- [x] All plan docs created and validated (`PLANNING_STATUS.md`).
- [ ] Resolve open questions (see `50`) before Phase 1 coding where blocking.

## Phase 1 — Core Infrastructure
- [ ] `pyproject.toml`, package skeleton (`src/aiagent/...` + tests).
- [ ] Config loader (YAML) for env/agents/tools/models with schema validation.
- [ ] Structured logger (JSON) with trace_id propagation.
- [ ] FastAPI app skeleton + `/healthz` + `/v1/projects` CRUD.
- [ ] API-key auth middleware (role-scoped).
- [ ] Alembic setup + migration 0001 (all tables from `28`).
- [ ] Secret store interface + encrypted local vault.
- [ ] Event outbox + dispatcher (in-process) + `event_stream`.
- [ ] Docker compose local (ctrl + pg + optional redis) + sandbox image build.
- [ ] Tests: unit (config, auth), integration (DB up/down), API health.

## Phase 2 — Agent Runtime
- [ ] Agent definition loader (YAML → dataclass) with permission field validation.
- [ ] Model client interface + OpenAI + Anthropic + Ollama adapters (+ MockModelClient).
- [ ] Model call loop w/ tool-call handling, streaming optional, token accounting.
- [ ] Output validation layer (schema + required-artifact check).
- [ ] Run state machine (CREATED→SUCCEEDED/FAILED...) with retry/backoff.
- [ ] Context injection placeholders (memory slots) — filled in Phase 5.
- [ ] Prompt versioning attached to run rows.
- [ ] Tests: mock-model end-to-end run; adapter smoke (optional real key).

## Phase 3 — Task System
- [ ] Task entity CRUD + state machine (`08`).
- [ ] Dependency DAG validation + cycle detection.
- [ ] In-process queue (priority/aging) + dispatcher with lease.
- [ ] File-scope write locks (per project workspace roots).
- [ ] Task approval fields + event emission (`task.*`).
- [ ] Tests: transitions, cycles, concurrent-dispatch lock behavior.

## Phase 4 — Workflow Engine
- [ ] Workflow definition loader (YAML) + schema.
- [ ] Step executor: agent / gate / fan_out / wait / emit / approval gate.
- [ ] Pause/resume + cancel semantics + idempotent step results.
- [ ] Timeouts per step and per run; retry policies for retryable steps.
- [ ] Approval-gate integration with `approval` service (packet creation + resume).
- [ ] Watchdog for stuck steps.
- [ ] Tests: 6-step workflow w/ gates; pause/resume; timeout handling.

## Phase 5 — Memory
- [ ] Memory tables + CRUD service for project/task/org layers.
- [ ] Embedding client (one embedding model) + pgvector store/search.
- [ ] Short-term episode storage + distiller.
- [ ] Context budget assembler (slot-filling from memory, capped).
- [ ] Tests: embed roundtrip; retrieval; budget cap enforcement.

## Phase 6 — Tool System + Sandbox
- [ ] Tool registry + schema; Permission Guard (fail-closed).
- [ ] Sandbox gatekeeper (docker) + warm pool + limits + cleanup.
- [ ] Tools: read_file, write_file, list_dir/glob, run_terminal (auditor),
       git_status/diff/commit, run_tests, exec_python.
- [ ] web_search + web_fetch tools behind egress allowlist (research agents).
- [ ] deny-list + path-scope + egress policy enforcement tests.
- [ ] Integration tests against real docker sandbox (small suite).

## Phase 7 — Autonomous Development
- [ ] Project repo init into sandbox workspace; branch strategy.
- [ ] Dev task → dev agent → write code/tests → run tests → commit.
- [ ] Review packet → reviewer verdict → change-request loop.
- [ ] Artifact recording (code patches, test reports).
- [ ] Merge protocol (pipeline gates, squash, snapshot, changelog).
- [ ] E2E mock test: "FastAPI hello-world with test" produced end-to-end.

## Phase 8 — QA & Security
- [ ] Per-layer test config for user projects (unit/int/api/e2e).
- [ ] Full suite runner + TestRun records + coverage gate.
- [ ] Bug triage + fix loop (max 3) with context escalation.
- [ ] SAST (bandit/semgrep), dependency audit, secret scan on repo.
- [ ] Fix loop terminates on deliberate-bug fixture.
- [ ] Security scan findings → task creation path.

## Phase 9 — Deployment
- [ ] Dockerfile generator + compose generation for user apps.
- [ ] Deploy to local env + health check + rollback on failure.
- [ ] deploy_record + env config + secret injection.
- [ ] Migration execution as part of deploy.
- [ ] Test: deploy hello-world; force fail → rollback.

## Phase 10 — Monitoring
- [ ] Metric counters + cost tracking + dashboard endpoints.
- [ ] Alerting rules (budget, sandbox, approval-stall, agent-fail).
- [ ] Incident lifecycle (open/ack/resolve/postmortem).
- [ ] Post-deploy monitoring config generator.
- [ ] Test: budget alert triggers; incident created on health fail.

## Phase 11 — Advanced Autonomy
- [ ] Full project_build workflow non-interactive on greenfield project.
- [ ] Retrospective + lesson injection.
- [ ] Org memory + knowledge templates for reuse.
- [ ] Multi-project portfolio handling.
- [ ] Cost optimization from model_call_log analytics.
- [ ] Test: greenfield project builds end-to-end without human code edits.

---

## Cross-Cutting Verification

| Area | Verify |
|---|---|
| Security | Permission Guard fail-closed; no secrets in logs; sandbox no egress by default |
| Cost | Budget hard caps enforced; model_call_log complete |
| Audit | bid/audit entries for every sensitive op; trace_id flows |
| Recovery | Crash restart resumes workflows; leases reclaimed |
| Observability | every gate/metric dashboard queries exist |