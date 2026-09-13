# STEP 5 — Agent Runtime (DONE)

Implements the provider-independent model abstraction plus the runnable,
persistent `AgentRun` execution path: gate checks, retry/backoff, cancellation,
risk-aware pause and content handling. **No** real tool execution, task/workflow
engine, queue or real-model credentials were added (STEP 5 stop rule); the only
provider shipped is the deterministic mock.

## Scope

1. Model abstraction (`runtime/`): `ModelProvider` protocol, `ModelRequest` /
   `ModelUsage` / `ModelResponse` (frozen dataclasses), `ModelProviderRegistry`,
   `ModelGateway.complete(...)` (validation → provider → normalization →
   timeout/cancellation handling), `CancelToken`.
2. `DeterministicMockModelProvider` (`mock` / `mock-default`) — scripted
   behaviors (`OK`, `OK_WITH_PREAMBLE`, `INVALID`, `TIMEOUT`, `SERVER_ERROR`,
   `RATE_LIMIT`, `CANCELLED`), deterministic payloads, tick-based cancellation.
3. `AgentRun` persistence: full state machine (plan 37) incl. **retry** and the
   documented **READY → PAUSED** extension for the approval gate; events, audit,
   new indexes, repository helpers (`next_attempt`, `find_agent_run`).
4. `AgentRuntimeService.run(request)` — resolution → config → gates → run
   lifecycle → execution w/ retry → outcome; `find_run`, `find_runs_in_state`.
5. Runtime gates: check status/capability/tool permissions/autonomy/input size /
   execution context (no tool execution — plan 11/12 only).
6. Prompt layering: `FileInstructionSource` (loads `config/prompts/<ref>.md`
   with traversal guard), system/user prompt builders, runtime constraint
   footer.
7. Content store: `ContentStore` caching — `MemoryContentStore` + file-backed
   `FileContentStore` under the artifacts dir (bounded inline preview +
   `output_truncated` flag, `file://` refs).
8. Internal HTTP API: `POST /internal/agents/{handle}/run`,
   `GET /internal/agent-runs/{run_id}` (mounted in `api/app.py`; STEP 4 error
   envelopes reused).
9. Config: `RuntimeSettings` in `core/config.py` + `default.yaml` / `dev.yaml`
   (default provider `mock`, input/output/inline-preview limits, retry policy).
10. Tests: offline unit (run-state, retry, mock, gateway, context, prompts,
    content) + integration (orchestration against real Mongo + HTTP API).

## Run state machine (`runtime/run_state.py`, plan 37)

```
                       +---> SUCCEEDED
     CREATED → READY → READY ──> RUNNING → VALIDATING ──┤
        │         │      │                               +---> FAILED (final)
        │        PAUSED  │       retry: FAILED → READY (re-attempt, same run row)
        │         │      │
        └─────────┴──────┴──> CANCELLED (terminal)
```

- CREATED → READY unless the autonomy/approval gate stops it → **READY → PAUSED**
  (documented STEP 5 extension; level < required, no model call made).
- RUNNING → VALIDATING only when output is non-empty after the completion gate.
- FAILED is always final *from execution*; a `FAILED(execution)` transitions to
  READY for retry while `retry_count < max_attempts` (same run row, attempt
  incremented, `agent_run.retrying` state event), otherwise the run stays FAILED
  with the terminal event. `CANCEL` is valid from CREATED/READY/PAUSED/RUNNING/
  VALIDATING; PAUSED/SUCCEEDED/FAILED/CANCELLED are terminal (no further state
  events). `_run_state_events` maps every (from,to) to its event; the service
  persists `AgentRunStatus` and `AgentRunState` fields in sync.
- Cancellation applies even during `wait_for` and while sleeping for a retry
  backoff (token checked between attempts).

## Model abstraction (`runtime/models.py`, `gateway.py`)

- `complete(provider, request, *, cancel_token, timeout_secs)`:
  validate provider/config → resolve via registry (unknown provider →
  `ProviderNotFoundError` → `ModelConfigurationError` at the service) → call
  within `asyncio.wait_for` → normalize to `ModelResponse`.
- Provider results pass through a completion gate: empty/whitespace text →
  `InvalidModelResponseError` (non-retryable validation); gateway wraps the
  generic `Exception` into `TransientProviderError` but lets typed `ModelError`
  pass (fixed during testing so `SERVER_ERROR` surfaces as
  `provider_unavailable`, not a transient wrapper).
- Timeouts: `asyncio.TimeoutError` → `ProviderTimeoutError` (retryable);
  `asyncio.CancelledError` / `ProviderCancelledError` (raised by the mock when
  the cancel token is set mid-call) propagate as cancellation, not retry.
- Determinism (testing): mock output `"[mock:model=<model>] ## Input <text> ->
  ok"` for OK; token estimates from prompt/response lengths.

## Retry / backoff (`runtime/retry.py`)

- Only `is_retryable` errors retry: `ProviderUnavailableError`,
  `ProviderTimeoutError`, `ProviderRateLimitError`, `TransientProviderError`.
- `compute_backoff(policy, attempt, rand)` = `min(cap, base*2**(attempt-1))`,
  optional full jitter; GAILAArticle

feedback (exit) → next attempt only up to `max_attempts` (default 3).
- Policy from the agent's `model.retry_policy` (the `retry_policy` block) or the
  runtime default (`RuntimeSettings.retry`); dev.yaml lowers the base/cap so
  retries are observable quickly (0.05s/0.2s). Backoff sleep honors the cancel
  token (short tick loop).

## Config & scaling (`core/config.py`)

- `RuntimeSettings.retry`, `max_input_chars` (200 000), `max_output_chars`
  (100 000), `inline_preview_chars` (4000), `default_provider` ("mock"),
  `default_model` ("mock-default"), `provider_timeout_secs` (180),
  `cancellation_poll_secs`; `StorageSettings.prompts_dir` points at
  `config/prompts` (default), artifacts under `data/artifacts`.

## Runtime gates (`runtime/context.py`, `service.py`)

| Gate | Failure |
|------|---------|
| `check_status` (ACTIVE) | `AgentNotExecutableError` 403 |
| `check_capability` (capability present) | `CapabilityNotConfiguredError` (403) |
| `check_permissions` (can use tool READ) | `PermissionDeniedError` 403 |
| `check_autonomy` (agent ≥ required) | resume falsely → paused w/o model call |
| `validate_input_size` (≤ max) | `PayloadTooLargeError` 413 (no run created) |
| execution context (project/task/workflow ids) | `InvalidExecutionContextError` 422 |
| model config (provider registered) | `ModelConfigurationError` (pre-raise, no run) |

`RuntimeRequest` carries `agent_handle`, `text_input`, `tool_requests`,
`required_autonomy_level`, `project_id`, `task_id`, `workflow_run_id`,
`correlation_id`, `timeout_secs`; the runtime refuses inputs larger than the
config limit (also truncates the inline preview in persisted runs).

## Content store (`runtime/content.py`)

- Memory + file-backed stores; `preview_text` keeps the first
  `inline_preview_chars` and appends `\n[truncated]`; `output_truncated` flag is
  set when the full output exceeds the preview bound. Large outputs are kept on
  disk (`<artifacts>/runs/<run_id>/<kind>.txt`) with a `file://` ref instead of
  being inlined.

## Prompt layering (`runtime/prompts.py`)

- `FileInstructionSource` loads `config/prompts/system/<agent>/v1.md` per
  `system_prompt_ref` (ref sanitized via `^[a-zA-Z0-9._/-]+$` + ".." ban);
  missing files → `None` (no error).
- System prompt = "{agent} wants", instructions, constraint footer (autonomy,
  allowed tools, artifact paths); user prompt = task text + optional tool
  requests + instructions/token caps. The seeded prompt files under
  `config/prompts/system/*/v1.md` are exercised in live runs.

## Internal API (`api/routers/runtime.py`)

- `POST /internal/agents/{handle}/run` — resolves slug→agent_id (repository
  lookup; the internal routes exist on the same app; STEP 4 API tests revealed
  routers are mounted **without** the `/v1` prefix), runs the agent, returns
  `envelope.ok(...)` with run outcome (`decision`, `status`, tokens, output,
  refs, retry/error fields). `approval_required` returns HTTP 200 with
  `decision=approval_required`, run `paused`. Errors reuse STEP 4 handlers:
  403 `agent_not_executable` / `permission_denied`, 404 `not_found`, 413
  `payload_too_large`, 422 `invalid_execution_context` / `validation_error`.
- `GET /internal/agent-runs/{run_id}` — `NotFoundError` → 404.

## Tests (`tests/unit`, `tests/integration`)

- 7 offline unit modules (~55 tests): state matrix incl. PAUSED + retry edge,
  backoff math (linear/capped/jitter/seed), mock script behaviors, gateway
  (registry, unknown provider, timeout, empty response, cancellation,
  wall-clock timeout with `tick_secs`), gates & context fields, File prompt
  source (load/missing/traversal), content stores + preview.
- `tests/integration/test_agent_runtime.py` (20 tests, real Mongo): success +
  persisted events/audit, attempts increment, slug/agent_id resolution,
  project/task/workflow/correlation metadata, disabled/capability/tool denials,
  bad context refs, oversize input, invalid provider config (no orphaned run),
  approval-required pause, retries (success after 2, exhaustion `retry_count=2`
  → FAILED with `provider_unavailable`, rate-limit, timeout-then-success),
  cancellation → CANCELLED.
- `tests/integration/test_runtime_api.py` (5 HTTP tests, STEP 4 pattern:
  `_mongo_available()` skip, per-test `_reset_db()`, `with _client() as c:` to
  trigger the lifespan): successful run → `GET` round-trip, approval pause,
  disabled 403 envelope, missing agent 404, unknown run 404.

## Verification results

| Gate | Command | Result |
|------|---------|--------|
| Format | `black src tests` | clean |
| Lint | `ruff check src tests` | clean (0 errors) |
| Types | `mypy src` | clean (55 files) |
| Tests | `pytest` | **232 passed** (152 offline + 80 integration) |
| Seed | `python -m aiagent.agents` | 8 agents active; rerun no-op |
| Live | uvicorn + `/internal/agents/backend-developer/run` | `succeeded`, `allowed`, mock output, persisted run w/ events `created,ready,claimed,started,succeeded` + audit |
| Live | approval window (level 2, required 3) | `approval_required`, `paused`, no model call |
| Live | disable → run → re-enable | 403 `agent_not_executable`; run succeeds again |
| Secrets | src/tests/docs scan | clean |

## Issues found and resolved

- Mock `SERVER_ERROR` was wrapped into a transient error by the gateway catch-all
  → typed `ModelError` now passes through (`except ModelError: raise`) so error
  codes stay precise (`provider_unavailable`).
- STEP 4 API suites reveal routers are mounted without `/v1` prefix → runtime
  API tests use bare `/internal/...` (documents actual routing).
- TestClient lifespan: API tests must use `with _client() as c:` so `init_db`
  runs (otherwise "database not initialized").
- AI-Agent tests import `ModelConfigurationError` from `runtime.errors` (not
  core); `ProjectService.create_project` requires an existing organization, so
  metadata tests seed an org first.
- Registering an agent directly as `disabled` is rejected by the registry
  policy → API/integration tests disable it after enabling (valid lifecycle).

## Decisions requiring approval

1. Retried runs reuse the **same** run row (attempt++ / `retry_count`, events
   `agent_run.retrying`); no new CREATED runs per attempt — observability wants
   one run per user call.
2. Exhausted retries end **FAILED** (not ESCALATED — plan 43); promoting runs
   to human escalation is deferred to the human-in-the-loop step.
3. **READY → PAUSED** added as a documented extension to plan 37 (§3) so
   approval-required runs are observable (paused) instead of silently "waiting".
4. Model request/response types are frozen dataclasses + `ModelProvider`
   protocol (not pydantic schemas) — the gateway boundary is internal.
5. Provider set is `mock` only in STEP 5; real providers (openai/azure/anthropic)
   are added later without changing the public request/response shape.
6. Content is file-backed under `data/artifacts` with bounded inline previews;
   no object storage in STEP 5.
7. Internal API carries no auth in STEP 5 (existing STEP 4 posture); auth is a
   separate concern.