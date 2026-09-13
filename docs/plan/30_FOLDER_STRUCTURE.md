# 30 — FOLDER STRUCTURE

Design rationale: **modular monolith** — all code in one repository; modules isolated by
namespace; module boundaries enforced by linting and import rules. Key principle: the
orchestrator module **must not** import from the agent runtime module (only interfaces).

---

```
ai-agent-company/
│
├── README.md
├── pyproject.toml                    # single dependency group; deps per optional group
├── Makefile                          # dev shortcuts (migrate, test, run)
│
├── src/
│   ├── aiagent/                      # root package
│   │   ├── core/                     # foundational (config, logging, error types, clock)
│   │   ├── orchestrator/             # CEO stage logic, gate decisions, dispatching
│   │   ├── workflow/                 # workflow definitions + engine
│   │   ├── tasks/                    # task state machine, queue, assignment
│   │   ├── agents/                   # agent runtime, prompt engine, model call loop
│   │   ├── model_router/             # provider abstraction, model selection
│   │   ├── memory/                   # memory CRUD, vector indexing, injection
│   │   ├── knowledge/                # knowledge base CRUD + retrieval
│   │   ├── tools/                    # tool registry, guard, tool implementations
│   │   ├── sandbox/                  # container lifecycle, gatekeeper
│   │   ├── artifacts/                # artifact CRUD, storage adapter
│   │   ├── approval/                 # approval packet creation, dispatch, decision
│   │   ├── events/                   # event bus, outbox, dispatcher
│   │   ├── monitoring/               # platform metrics, alert dispatcher
│   │   ├── security/                 # secret store interface, scrubber, policy checkers
│   │   ├── deployments/              # environment config, deploy record
│   │   └── api/                      # FastAPI app, routers, schemas, websocket
│   │
│   └── cli/                          # CLI entry points (thin wrappers over api)
│
├── config/                           # YAML/TOML configuration (agent defs, workflow defs, model registry)
│   ├── agents/                       # one file per agent definition (YAML)
│   │   ├── ceo_orchestrator.yaml
│   │   ├── pm_product_manager.yaml
│   │   ├── dev_backend.yaml
│   │   └── ...
│   ├── workflows/                    # workflow definitions
│   │   ├── project_build.yaml
│   │   └── bug_fix_loop.yaml
│   ├── models.yaml                   # model registry + routing profiles
│   ├── tools.yaml                    # tool registry + permissions
│   ├── projects/                     # per-project default config
│   └── env/                          # environment-specific config
│       ├── dev.yaml
│       ├── staging.yaml
│       └── prod.yaml
│
├── prompts/                          # system prompt templates per agent role
│   ├── common/                       # shared instruction blocks (e.g., file handling rules)
│   └── agents/
│       ├── pm_product_manager.md
│       ├── dev_backend.md
│       ├── qa_code_reviewer.md
│       └── ...
│
├── db/
│   ├── migrations/                   # 0001_init.sql ...
│   ├── seeds/                        # optional seed data (knowledge templates)
│   └── test_fixtures/
│
├── knowledge/                        # seed knowledge base content (as files for db seeder)
│   ├── templates/                    # project templates, prd template
│   ├── playbooks/                    # fastapi-app.md, react-app.md, ...
│   ├── standards/                    # git-workflow.md, code-style.md
│   └── lessons/
│
├── deploy/
│   ├── docker/                       # Dockerfiles for control plane + sandbox base
│   │   ├── Dockerfile.ctrl
│   │   └── Dockerfile.sandbox
│   └── environments/                 # per-env compose / infra config
│       ├── local/docker-compose.yaml
│       ├── staging/
│       └── prod/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── test_fixtures/                # test DB fixtures, mock models
│
├── docs/                             # design docs, ADRs (if separate from planning)
│   ├── plan/                         # ← planning docs (this folder)
│   ├── adr/                          # Architecture Decision Records
│   ├── diagrams/
│   └── operations/
│
└── scripts/                          # dev scripts: bootstrap, migrate, seed, lint
```

---

## Module Dependency Rules

```
API → orchestrator, tasks, agents, approvals, artifacts, events
orchestrator → workflow, tasks, approvals, events, knowledge, artifacts
workflow → tasks, agents, approvals, tools, sandbox, events
tasks → (no dep on agents; runtime invokes via interface)
agents → tools (interface only), model_router, memory, artifacts
model_router → core, security (for secrets)
tools → sandbox (execution), security (guard), core
sandbox → core, security (secrets injection)
events → core (interfaces only)
monitoring → events (consumes)
memory/knowledge → core (embeddings abstraction)
```

No circular dependencies. Module boundaries enforced via lint rule (optional for MVP, hard
for v1).