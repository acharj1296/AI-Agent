# 40 — TEST STRATEGY

---

## 1. Layers (platform, not user project)

| Layer | Tools | Scope | Gate |
|---|---|---|---|
| Unit | pytest | core modules (orchestrator logic, guards, state machines, memory) | pre-commit + CI |
| Component | pytest | module boundaries via dep injection (task system ↔ runtime) | CI |
| Integration | pytest + testcontainers | DB migrations, event outbox, sandbox gatekeeper (docker) | CI |
| API contract | httpx | every endpoint against spun control plane | CI |
| E2E | pytest + real PG | full workflow run with **mock model** (fast, deterministic) | CI |
| E2E-real | pytest (opt-in, needs key) | full workflow with real provider on a tiny project | nightly/on-demand |
| Security | bandit, pip-audit, ruff rules | static scan of platform code | CI |
| Perf smoke | locust | API latency budget | on release |

---

## 2. Testing Principles

- **Determinism:** run state and time are injected as fakes in unit tests; no sleeps.
- **Model abstraction:** a `MockModelClient` returns scripted responses; used by CI.
- **DB isolation:** each test gets its own schema/transaction (transaction rollback pattern).
- **Sandbox:** integration tests use the real sandbox only for a small suite; the bulk uses a
  `FakeSandbox` that shells locally with the same guard.
- **Seed fixtures:** agents (YAML), workflows (YAML), one sample project.

---

## 3. Coverage Targets (platform)

| Scope | Line | Branch |
|---|---|---|
| core, tasks, workflow, agents | 85% | 75% |
| tools guard, approval, memory | 85% | 75% |
| sandbox wrapper | 70% | 60% |
| api | 80% | 70% |

Coverage measured over the diff on CI; enforced by `--cov-fail-under` per module group.

---

## 4. Real-Provider Gate

A nightly job runs `E2E-real` on a tiny fixture project (if a key is configured). Failures
are real bugs (unlike mock). Outputs: pass/fail + token usage + cost, fed to cost tuning.

---

## 5. Platform Test Matrix (per commit)

```
lint (ruff) → type (mypy) → unit → component → integration → api → e2e(mock) → security scan
```

Merge to main blocked unless all gates pass (post-merge: full integration rerun).

---

## 6. QA for User Projects

User-project testing operates through the test/QA system defined in `21_TESTING_SYSTEM.md`
within the sandbox; this document concerns the platform's own quality.

---

## 7. Test Data Management

- Fixtures under `tests/test_fixtures/`; no secrets; synthetic project names.
- Factory functions (factories) for tasks/agents/runs to keep tests compact.