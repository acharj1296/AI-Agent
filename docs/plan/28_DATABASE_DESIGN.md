# 28 — DATABASE DESIGN

---

## 1. Technology

- **PostgreSQL 16** with extensions: `uuid-ossp`, `pgcrypto`, `pgvector`.
- Rationale: single dependency, JSON + relational, vector search built-in, mature.

---

## 2. Core Entities (relational model)

### 2.1 Project

```sql
project {
  id uuid PK,
  name text,
  description text,
  stage text,          -- canonical stage enum
  autonomy_level int,
  status text,         -- active|paused|blocked|completed|cancelled
  config jsonb,        -- budgets, retryPolicy, providers, env configs
  created_by uuid,
  created_at timestamptz,
  updated_at timestamptz
}
```

### 2.2 Agent

```sql
agent {
  id uuid PK,
  agent_id text UNIQUE,  -- e.g. "dev_backend"
  department text,
  config jsonb,          -- full agent definition (schema in 04)
  created_at, updated_at
}
```

### 2.3 Agent Run

```sql
agent_run {
  id uuid PK,
  task_id uuid FK,
  agent_id uuid FK,
  attempt int,
  status text,          -- CREATED|READY|CLAIMED|RUNNING|VALIDATING|SUCCEEDED|FAILED|ESCALATED|PAUSED|CANCELLED
  parent_run_id uuid,   -- for spawned sub-agents
  model_id uuid,
  tokens_in int,
  tokens_out int,
  cost_usd numeric,
  tool_calls jsonb,     -- summary (not full log; full in event log)
  error_detail jsonb,
  started_at, completed_at
}
```

### 2.4 Task

```sql
task {
  id uuid PK,
  project_id uuid FK,
  type text,
  title text,
  description text,
  priority text,          -- critical|high|medium|low
  status text,
  parent_task_id uuid,    -- subtasks
  assigned_agent_id uuid,
  reviewer_agent_id uuid,
  dependencies uuid[],    -- or join table
  inputs uuid[],          -- artifact ids
  expected_outputs uuid[],
  approval jsonb,         -- {required, status, required_by, decision}
  estimate jsonb,
  retry_count int,
  failure_reason text,
  write_scope text,       -- for file-lock serialization
  cost_usd numeric,
  created_at, updated_at, started_at, completed_at
}
```

### 2.5 Artifact

```sql
artifact {
  id uuid PK,
  project_id uuid FK,
  name text,
  kind text,
  version int,
  uri text,
  hash text,
  producer_run_id uuid,
  status text,           -- draft|final|superseded|archived
  derived_from uuid[],
  approvals uuid[],
  meta jsonb,
  created_at, updated_at
}
```

### 2.6 Workflow Run

```sql
workflow_run {
  id uuid PK,
  project_id uuid FK,
  workflow_id text,
  status text,           -- RUNNING|PAUSED|COMPLETED|FAILED|CANCELLED
  current_step_stack jsonb,
  step_results jsonb,    -- map step_id → result summary
  created_at, updated_at
}
```

### 2.7 Approval

```sql
approval {
  id uuid PK,
  project_id uuid FK,
  task_id uuid,          -- nullable
  workflow_run_id uuid,
  tier text,             -- T0..T3
  title text,
  description text,
  material jsonb,        -- artifact ids, diffs, decision docs
  status text,           -- pending|approved|rejected|overridden|cancelled
  decision jsonb,        -- {user_id, comment, at}
  created_at, decided_at
}
```

### 2.8 Memory

```sql
mem_project|mem_task|mem_org|mem_agent_longterm|mem_conversation|mem_episode {
  id uuid PK,
  project_id uuid,      -- NULL for org-level
  task_id uuid,         -- for task memory
  kind text,
  content text,
  embedding vector(1536),  -- nullable
  source_run_id uuid,
  confidence float,
  access_scope text,
  created_at timestamptz
}
```

### 2.9 Event + Outbox + Trace

```sql
event_outbox { id uuid PK, payload jsonb, processed bool, created_at }
event_stream { id uuid PK, seq bigserial, type text, payload jsonb, project_id, emitted_by jsonb, trace_id, created_at }
span { id uuid PK, trace_id, parent_span_id, name, start_ms, end_ms, attrs jsonb }
```

### 2.10 Audit Log

```sql
audit_log {
  id uuid PK, ts timestamptz, action text, subject text, project_id uuid,
  resource_type text, resource_id uuid, before jsonb, after jsonb, trace_id
}
```

### 2.11 Supporting Tables

```sql
test_run { id, project_id, task_id, commit_sha, filter, status, tests jsonb, duration_ms, created_at }
deploy_record { id, project_id, env, version_label, status, commit_sha, decision_id uuid, created_at }
model_call_log { id, task_id, run_id, model_id, tokens_in, tokens_out, cost_usd, latency_ms, retries, created_at }
cost_snapshot { id, project_id, usd_total, snapshot_at }
incident { id, project_id, category, severity, status, trigger_event_id, opened_at, resolved_at }
```

### 2.12 Identity, Communication & Registry Entities

```sql
organization {
  id uuid PK,
  name text,
  autonomy_default int,        -- org-wide default level (45)
  budgets jsonb,               -- org budget caps
  settings jsonb,
  created_at
}

user {
  id uuid PK,
  org_id uuid FK,
  name text,
  email text UNIQUE,
  role text,                   -- admin | reviewer | observer
  api_key_hash text,           -- scoped hash, never raw
  created_at, last_seen_at
}

message {                      -- governed inter-agent / agent-human messages (15)
  id uuid PK,
  project_id uuid FK,
  trace_id uuid,
  type text,                   -- info.request | info.response | approval.packet | notify
  sender text,                 -- agent_id | system | user:<id>
  recipient text,              -- agent_id | system | channel (email/webhook)
  payload jsonb,
  status text,                 -- pending | delivered | failed
  created_at, delivered_at
}

tool_call {
  id uuid PK,
  run_id uuid FK,
  tool_id text,
  args jsonb,
  status text,                 -- allowed | denied | ok | error | timeout
  result_size_bytes int,
  started_at, completed_at
}

review {                       -- code/artifact review record (22)
  id uuid PK,
  task_id uuid FK,
  reviewer_agent_id uuid,
  verdict text,                -- approve | request_changes | block
  findings jsonb,              -- ReviewFinding[]
  confidence float,
  comment text,
  created_at
}

environment {                  -- deploy targets (23)
  id uuid PK,
  project_id uuid FK,
  name text,                   -- local | staging | prod
  config jsonb,                -- target config (non-secret)
  deployment_approval_tier text,  -- T2 | T3
  created_at
}

model {                        -- model registry (12)
  id uuid PK,
  model_id text UNIQUE,        -- e.g. "gpt-4o-mini"
  provider text,               -- openai | anthropic | google | ollama | vllm
  capability jsonb,            -- {tool_calls, context_size, quality_rank}
  cost_per_1k jsonb,           -- {in, out}
  latency_ms_est int,
  enabled bool,
  privacy_local bool           -- true = data stays on-prem (local models)
}

provider_call_log {            -- audit of provider requests (18)
  id uuid PK,
  model_id uuid FK,
  project_id uuid FK,
  run_id uuid,
  outcome text,                -- ok | retried | fallback | failed
  fallback_from text,
  http_status int,
  created_at
}
```

---

## 3. Join / Lookup Tables

- `task_dependency`: (task_id, depends_on_task_id) — enables cycle detection queries.
- `knowledge_entry`: (id, title, body, tags, audience, status, embedding, version).
- `provider_api_key`: (id, provider, key_encrypted, org_id, quota_monthly).

---

## 4. Indexes

- `(project_id)` on all project-scoped tables.
- `(task_id, status)` on agent_run.
- `(project_id, stage)` on project.
- GIN index on `task.dependencies` (array) and `approval.status`.
- HNSW index on embedding columns for vector search.
- BRIN index on `ts` in audit_log and event_stream (time-ordered).
- Unique constraint: `(project_id, name, version)` on artifact.

---

## 5. Migrations

- Versioned forward-only migrations under `db/migrations/0001_*.sql`, `0002_*.sql`.
- Tests validate forward migration + down script each CI cycle.

---

## 6. Data Ownership Boundaries

| Module | Tables it owns | others read/write |
|---|---|---|
| Orchestrator | project, approval, incident | read-only for agents |
| Task System | task, task_dependency | read by agents |
| Agent Runtime | agent_run, model_call_log | read by observability |
| Artifact System | artifact | read by all |
| Memory System | mem_* | read/written by agent runtime + memory mgr |
| Workflow Engine | workflow_run, event_outbox/event_stream | read by observability |
| Observability | span, audit_log, cost_snapshot | append-only from all |
| Knowledge | knowledge_entry | read by all; write by orchestrator/knowledge_writer only |