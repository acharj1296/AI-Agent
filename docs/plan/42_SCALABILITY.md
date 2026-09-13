# 42 — SCALABILITY

---

## 1. Current Limits (MVP design)

- 1 control-plane process (async) managing N workers in-process.
- 1 PostgreSQL.
- Sandbox pool: 4 warm containers.
- Task dispatcher single-threaded claim loop (fine for ≤100 tasks/min).

---

## 2. Growth Paths

### 2.1 More tasks / more agents
- Scale **workers** horizontally: control-plane workers run as separate containers sharing
  PG + object store; task claim loop becomes distributed via `pg_advisory_lock` on
  task claim (v1).

### 2.2 More projects
- **Multi-project isolation:** one control-plane process can host many projects; each
  project has its own sandbox pool (resource caps per project).
- Tenant isolation (v1) via project-scoped auth tokens.

### 2.3 More model calls
- Model clients are stateless; concurrency via async.
- Rate-limit awareness: client wraps provider rate limits with retry/queue.

### 2.4 Large repos / artifacts
- Git LFS or object storage for big artifacts; clone-on-demand shallow + sparse checkout.

---

## 3. Bottleneck Analysis (v0)

| Bottleneck | Mitigation |
|---|---|
| Model cost / latency (biggest) | model routing, budgets, caching (26) |
| DB contention on event log | outbox batching; index tuning; archiving hot tables |
| Sandbox provisioning | warm pool, image caching, parallel pools |
| Human approval stall | reminder + timeout policies (17) |
| Long workflows | checkpointing; resumable runs (07) |

---

## 4. Metrics to Watch

- task queue depth, worker utilization, sandbox warm pool availability, model latency
  percentiles, approval pending age, DB connection saturation.

---

## 5. Horizontal Scaling Design (v1)

```
[LB] → ctrl API replicas (stateless; session affinity not needed)
  ↓
[PG primary + replicas (reads)]      ← event subscribers on streams
  ↓
[worker replicas] → pick tasks via advisory locks → sandbox pools
```

- Workers scale independently; no in-process queue (Redis streams adopted in v1).
- Object-store single writer per artifact version (idempotent by hash).

---

## 6. Limits & Config

All in `project.config` + org config; defaults in `config/env/*.yaml`. Every limit is
enforced (hard fail with clear event) not just warned.