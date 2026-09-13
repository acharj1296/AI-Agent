# 31 — TECH STACK

---

## 1. Backend

| Choice | Rationale | Alternatives | Disadvantages |
|---|---|---|---|
| **Python 3.12** | Rich AI ecosystem; fast dev; async support; pgvector client libs | Rust (faster), TypeScript (same team) | GIL (mitigated by async + process isolation), slower than Rust |
| **FastAPI** | Native async, Pydantic validation, OpenAPI auto-gen, WebSocket support | Flask, Django, Litestar | Slightly newer; async ecosystem still maturing |
| **SQLAlchemy 2.0 + asyncpg** | Mature ORM, async, Pydantic integration | Peewee, raw SQL, Tortoise | Learning curve; migrations via Alembic |

---

## 2. Database

| Choice | Rationale | Alternatives | Disadvantages |
|---|---|---|---|
| **PostgreSQL 16 + pgvector** | One DB for relational + vector; JSON support; mature | PG + separate Pinecone, MongoDB | Multi-process writes can require pooling tuning |
| **Alembic** (migrations) | Standard for SQLAlchemy; supports versioned forward-only | Django migrations (if Django) | — |

---

## 3. Task Queue / Event Transport

| Choice | Rationale | Alternatives | Disadvantages |
|---|---|---|---|
| **In-process async queue + PG outbox** (MVP) | Zero external infra; SQL-persistent; simple | Redis Streams, Celery, NATS | No cross-process scaling until Redis adopted |
| **Redis Streams** (v1 option) | High throughput, Pub/Sub, consumer groups | — | Extra infrastructure |

---

## 4. Model Client

| Choice | Rationale | Alternatives |
|---|---|---|
| **LiteLLM** (proxy abstraction) | OpenAI/Anthropic/Google/Ollama unified interface, local fallback | Raw SDK calls per provider; LangChain |
| **Ollama** | Local model hosting; key for cost control + privacy | vLLM (more efficient, heavier), cloud-only |

---

## 5. Vector Store

| Choice | Rationale | Alternatives |
|---|---|---|
| **pgvector** (via PG) | Single DB; no extra infra; HNSW indexing | Pinecone, Weaviate, ChromaDB, Qdrant |

---

## 6. Sandboxing

| Choice | Rationale | Alternatives | Disadvantages |
|---|---|---|---|
| **Docker** (rootless where possible) | Mature, resource limits, networking | gVisor/Firecracker (heavy setup), nsjail | Socket access from host requires care |
| **Docker Compose** (local deploy) | Simple multi-service local setup | K3s, Docker Swarm | Not prod-ready (MVP is local only) |

---

## 7. Object Storage

| Choice | Rationale | Alternatives |
|---|---|---|
| **Local filesystem** (MVP: `./data/artifacts/`) | Zero dependencies for MVP | MinIO (S3-compatible) |
| **MinIO** / S3 (v1) | S3 API standard; scalable | GCS, Azure Blob |

---

## 8. Auth

| Choice | Rationale | Alternatives |
|---|---|---|
| **API-key based** (MVP) | Simple; single-org local system | OAuth2/OIDC (v1, multi-user) |

---

## 9. Frontend

| Choice | Rationale | Alternatives |
|---|---|---|
| **None (MVP)** — REST/WS + CLI only | Keep scope tight | Next.js + React (v1 dashboard) |
| **Next.js + shadcn/ui** (v1) | Fast dev; component ecosystem | Remix, plain React |

---

## 10. Testing

| Tool | Use |
|---|---|
| pytest + pytest-asyncio | unit + integration (Python) |
| httpx / pytest-httpserver | API contract tests |
| vitest / Jest | user project JS tests (inside sandbox) |
| Playwright (sandboxed) | E2E (if user app is web) |
| bandit + pip-audit | security |
| locust / pytest-benchmark | performance |
| ruff + black | lint/format |
| mypy | type checking |
| pre-commit | commit hooks |

---

## 11. Dev Tooling

| Tool | Use |
|---|---|
| Makefile / just | shortcuts |
| docker + docker-compose | local env |
| Alembic | DB migrations |
| pgadmin4 or psql | local DB admin |

---

## 12. Deployment (MVP)

- Local: `docker-compose up` with 4 services (ctrl, pg, redis?, sandbox-pool).
- No cloud infra in MVP.
- Image builds in CI (GitHub Actions) only if user wants; local builds fine.

---

## 13. Decision Summary (Locked)

- Language: Python
- API framework: FastAPI
- DB: PostgreSQL 16 + pgvector
- ORM: SQLAlchemy 2 + Alembic
- Task queue: in-process (MVP) → Redis (v1)
- Model router: LiteLLM proxy
- Local model: Ollama
- Sandbox: Docker
- No frontend (MVP)
- Tests: pytest

These decisions are revisited if they block a core capability.