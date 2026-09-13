# 29 — API DESIGN

---

## 1. Architecture

- **REST + JSON** (OpenAPI 3.1) for the control-plane API.
- **WebSocket** for streaming: agent run events, workflow progress, live approval packets.
- **CLI** consumes the same REST API (thin CLI wrapper).
- **Frontend** (v1) consumes the same REST API.

---

## 2. API Modules & Key Resources

### 2.1 Projects

| Method | Path | Description |
|---|---|---|
| POST | `/projects` | create project (intake payload) |
| GET | `/projects` | list projects |
| GET | `/projects/:id` | project detail + state |
| PATCH | `/projects/:id` | update config/status |
| DELETE | `/projects/:id` | archive/cancel |
| GET | `/projects/:id/stage` | current stage + history |
| POST | `/projects/:id/pause` | pause |
| POST | `/projects/:id/resume` | resume |
| POST | `/projects/:id/rollback` | rollback to snapshot |
| GET | `/projects/:id/snapshots` | list snapshots |

### 2.2 Tasks

| Method | Path | Description |
|---|---|---|
| GET | `/projects/:id/tasks` | list (filter by status/type/agent) |
| POST | `/projects/:id/tasks` | create task (admin) |
| GET | `/tasks/:id` | task detail + history + cost |
| PATCH | `/tasks/:id` | update assignment/priority |
| POST | `/tasks/:id/retry` | manual retry |
| POST | `/tasks/:id/cancel` | cancel |
| POST | `/tasks/:id/approve` | reviewer approve (shortcut) |
| POST | `/tasks/:id/request_changes` | feedback |

### 2.3 Agents & Runs

| Method | Path | Description |
|---|---|---|
| GET | `/agents` | list agent definitions |
| GET | `/agents/:agent_id` | detail |
| GET | `/projects/:id/runs` | runs history (filterable) |
| GET | `/runs/:id` | run detail (logs, tools, cost, trace) |
| POST | `/runs/:id/retry` | manual re-run |
| GET | `/runs/:id/logs` | full run event log |

### 2.4 Artifacts

| Method | Path | Description |
|---|---|---|
| GET | `/projects/:id/artifacts` | list (filter kind/status) |
| GET | `/artifacts/:id` | metadata + versions |
| GET | `/artifacts/:id/versions` | version list |
| GET | `/artifacts/:id/versions/:v` | metadata for version |
| GET | `/artifacts/:id/versions/:v/download` | stream content (policy-gated) |
| POST | `/artifacts/:id/finalize` | draft → final |

### 2.5 Approvals

| Method | Path | Description |
|---|---|---|
| GET | `/approvals/pending` | list pending (org-wide) |
| GET | `/projects/:id/approvals/pending` | project-specific |
| GET | `/approvals/:id` | detail + material |
| POST | `/approvals/:id/approve` | human decision |
| POST | `/approvals/:id/reject` | human decision |
| POST | `/approvals/:id/override` | with modification note |

### 2.6 Workflows

| Method | Path | Description |
|---|---|---|
| GET | `/projects/:id/workflows` | list runs |
| GET | `/workflows/:id` | run detail + step tree |
| POST | `/workflows/:id/pause` | pause |
| POST | `/workflows/:id/resume` | resume |
| POST | `/workflows/:id/cancel` | cancel |

### 2.7 Deployments

| Method | Path | Description |
|---|---|---|
| GET | `/projects/:id/deployments` | list |
| GET | `/deployments/:id` | detail + health |
| POST | `/deployments/:id/rollback` | manual rollback trigger |
| POST | `/projects/:id/deploy` | trigger deploy (with approval) |

### 2.8 Observability

| Method | Path | Description |
|---|---|---|
| GET | `/metrics/project/:id` | cost, budget, task stats |
| GET | `/metrics/fleet` | agent health, model usage |
| GET | `/metrics/cost` | cost summary by time range |
| GET | `/projects/:id/events` | event stream (filterable) |
| GET | `/traces/:trace_id` | trace spans |

### 2.9 Auth & Config

| Method | Path | Description |
|---|---|---|
| POST | `/auth/login` | issue token (MVP: API key) |
| GET | `/config/models` | list models + availability |
| GET | `/config/agents` | list agent configs |
| PATCH | `/config/agents/:agent_id` | update agent config (requires human) |
| GET | `/config/budgets` | project budgets |
| PATCH | `/config/budgets` | update budgets (requires human) |

---

## 3. WebSocket Streams

| Channel | Topic | Payload |
|---|---|---|
| `project/:id/events` | task/agent events | event envelope |
| `runs/:id/stream` | agent run token stream | token deltas (optional, future) |
| `approvals` | pending approval | approval packet |

---

## 4. Response Envelope

```json
{
  "ok": true,
  "data": {},
  "meta": { "page": 1, "total": 10 },
  "trace_id": "uuid"
}
```
Error responses: `{ "ok": false, "error": { "code": "...", "message": "...", "details": {} } }`

---

## 5. Authentication & Rate Limiting

- MVP: API key in header (`X-API-Key`); scoped to org, role-based.
- Rate limiting: per-key sliding window (default 100 req/min for mutations, 500 for reads).
- Human-in-loop approval actions: rate-limit to prevent automated overrides.

---

## 6. Versioning

- URL path versioning `/v1/...` (only one version at a time in MVP; sunset headers in v1).