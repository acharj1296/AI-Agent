# 20 — CODE EXECUTION

---

## 1. Scope

Code execution covers: building the user's project, running tests, running the app locally,
and any scripted automation the workflows legitimately need. All executed inside the sandbox
(see `19`).

---

## 2. Execution Flow

```
run_spec {image, task_id, script|command, limits, env} 
  → gatekeeper validate (policy check)
  → container allocate
  → exec (script or command) with timeout + resource limits
  → collect stdout/stderr + exit code + artifacts
  → cleanup
```

---

## 3. Supported Execution Types (MVP)

| Type | Tool | Notes |
|---|---|---|
| shell command | run_terminal | auditor + timeouts |
| python script | exec_python | venv isolated per project |
| test suite | run_tests | pytest/JS runner config from project |
| build | run_build (devops) | npm build, pip build, etc. |
| service start | run_service | long-running process with health check |
| migration | run_migration | versioned migration runner |

---

## 4. Reproducible Environments

- **Base images** pinned by digest (Python 3.12-slim, Node LTS, etc.).
- **Dependency caches** mounted from a shared cache volume (checksum-keyed) to keep installs
  fast and consistent.
- **Lockfiles** mandatory: `requirements.txt` (hashes) / `package-lock.json` etc. enforced by
  a `lockfile_check` gate before merge.
- **Build numbers:** every execution stamped with commit sha + run id for traceability.

---

## 5. Test Execution Contract

- `run_tests` accepts: test command templates (from project config), target subset (unit /
  integration / e2e), and returns JUnit-compatible XML parsed to `TestRun` records.
- Failed tests produce structured `TestFailure` objects that map to **bug-fix tasks**
  (see `21_TESTING_SYSTEM.md`).
- Test runs are cached by `(commit_sha, test_filter, image_digest)`; skip reruns when cache
  hit (unless forced).

---

## 6. Service Runs & Health Checks

- Long-running services (server instances) run with `--healthcheck` probe of the app's
  `/health` endpoint; exit policy escalates on repeated failure.
- Port mapping is local-only within test namespace; not exposed to host unless explicitly
  configured (e.g., local deployment of user app for demo).

---

## 7. Code Execution Security Summary

| Control | Mechanism |
|---|---|
| Isolation | container + seccomp + cap-drop + non-root |
| Network | isolated/allowlist/local-only per task |
| Time | command timeout + run timeout |
| Resources | CPU/mem/pids/disk quotas |
| Integrity | pinned images, lockfiles, checksums |
| Audit | every exec logged; result provenance |

---

## 8. Failure Handling

- Non-zero exit → RUN failed with captured tail logs (≤ 4KB into memory; full log to artifact
  `build_log`).
- Timeout/OOM → retry once with same params (if retryable), else FAILED + escalate.
- Registration of long-running service instability → monitoring incident path (`24`).

---

## 9. Open Question

- Safe long-running **background task pools** for e.g. seed-data jobs; likely phase 8+.