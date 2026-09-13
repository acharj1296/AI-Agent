# 00 — MASTER PLAN

> Autonomy: the system described here is a **planning blueprint**, not existing software.
> This file is the single entry point. Read `docs/plan/PLAN_INDEX.md` for the reading order.

---

## 1. Project Objective

Build an **autonomous AI software development company** — a software system that can take a
business idea or software requirement and autonomously run it through a full product lifecycle:

intake → research → specification → architecture → planning → multi-agent development →
review → testing → security → deployment → monitoring → maintenance → improvement.

The system is **not a chatbot**. It is an **organization of specialized AI agents** modeled on
real software companies, coordinated by an orchestrator, driven by persisted state, a task
system, a workflow engine, and controlled human-in-the-loop approval gates.

---

## 2. Long-Term Vision

A user submits an idea. The system:

1. Clarifies the requirement (asking questions when needed).
2. Runs market / competitor / technical research.
3. Produces a validated product requirements document (PRD).
4. Produces an architecture and technology selection.
5. Decomposes work into milestones and tasks.
6. Deploys an organization of specialist agents to implement, review, test, and secure the
   product.
7. Deploys the result to a target environment.
8. Monitors, maintains, and improves the product over time.
9. Learns from past projects to improve future ones.

A human acts as **Board of Directors** — setting autonomy level, approving high-risk gates
(architecture, production deployment, external spend), and only intervening on escalations.

---

## 3. Core Capabilities

| Capability | Description |
|---|---|
| Idea intake & clarification | Structured intake form + clarifying question loop |
| Research | Web/market/competitor/technical research with cited sources |
| Validation | Feasibility, cost, and risk assessment before commitment |
| Specification | PRD, user stories, acceptance criteria, non-functional requirements |
| Architecture | System, database, security, and DevOps design |
| Planning | Milestones → epics → tasks, with dependencies and estimates |
| Orchestration | Workflow engine that routes tasks to the right agent at the right time |
| Multi-agent development | Specialized coding agents editing a real repository |
| Quality | Code review, unit/integration/E2E/security/performance testing, bug fixing |
| Delivery | CI/CD, environments, database migrations, rollback |
| Post-launch | Monitoring, incident handling, maintenance tasks, improvement loop |
| Learning | Post-project retrospective; update project templates and best practices |

---

## 4. System Boundaries

### In scope
- The orchestration, agent, task, workflow, memory, tool, state, and approval subsystems.
- Agents that plan, analyze, document, and write the code of *user* software projects.
- Code execution inside sandboxed environments.
- Deployment of user-built applications to configured environments.

### Out of scope
- The system does **not** build itself (no self-modification of the orchestration engine).
- No general web access beyond authenticated research tools.
- No interaction with non-authorized external SaaS without explicit credentials/config.
- No autonomous financial transactions without pre-approval budgets.

---

## 5. Major Components

| Component | Responsibility | Doc |
|---|---|---|
| Orchestrator (CEO) | Top-level workflow control, stage gates, escalation | 03, 05, 07 |
| Agent Runtime | Lifecycle, spawning, memory injection, tool sandbox | 06, 04 |
| Agent Definitions | Roles, prompts, permissions, capabilities | 35, 36, 37 |
| Task System | Task state machine, queue, assignment, dependencies | 08 |
| Workflow Engine | Business-process orchestration, gates, retries | 07 |
| Project State Store | Single source of truth for project data | 13 |
| Artifact System | Versioned artifact repository + pointers | 14 |
| Memory System | Short/long-term/project/org memory layers | 09 |
| Knowledge System | Org knowledge base, lessons learned, templates | 10 |
| Tool System | Registered, permissioned, sandboxed tools | 11, 19 |
| Code Execution | Isolated build/test/run environments | 20 |
| Model Routing | Provider-agnostic model selection by task/cost/quality | 12 |
| Event Bus | Async events between agents/components | 16 |
| Human Approval | Configurable autonomy gates | 17, 45, 46 |
| Observability | Logs, metrics, traces, cost accounting | 27 |
| Secrets & Security | Secret store, RBAC, threat model enforcement | 18, 39 |
| Data Persistence | PostgreSQL + vector store (see 28) | 28 |

---

## 6. Agent Organization (Target)

```
Board (Human)  — autonomy levels, approvals, escalation
│
└── Orchestrator (CEO)
    ├── Product Dept      : Product Manager, Business Analyst, Requirements Agent
    ├── Research Dept     : Market Research, Competitor Research, Technical Research
    ├── Architecture Dept : System, Database, Security, DevOps Architect
    ├── Development Dept  : Frontend, Backend, Database, API, Integration
    ├── Quality Dept      : QA Lead, Test Automation, Code Review, Security Test, Perf Test
    ├── DevOps Dept       : CI/CD, Deployment, Infrastructure, Monitoring
    └── Management        : Project Manager, Progress Manager, Decision/Approval Agent
```

See `04_AGENT_ARCHITECTURE.md` and `05_AGENT_ROLES.md` for the final canonical hierarchy.
Controlled communication is enforced: agents do **not** freely message each other; they
exchange via the orchestrator, task system, event system, shared project state, and artifact
system (least-privilege principle).

---

## 7. End-to-End Lifecycle

```
IDEA → INTAKE → RESEARCH → VALIDATION → PRD → ARCHITECTURE → ROADMAP →
TASK GENERATION → TASK ASSIGNMENT → DEVELOPMENT → CODE REVIEW → TESTING →
BUG FIXING → SECURITY → DEPLOYMENT → MONITORING → MAINTENANCE → IMPROVEMENT
```

Detailed in `38_PROJECT_PIPELINE.md`. Stage gates and approvals in `17_HUMAN_APPROVAL.md`.

---

## 8. Development Phases

| Phase | Deliverable |
|---|---|
| 0 | This planning system (done) |
| 1 | Core infrastructure: repo skeleton, DB, config, secrets, observability |
| 2 | Agent runtime: agent lifecycle, prompt engine, basic single-thread execution |
| 3 | Task system: state machine, queue, assignment, persistence |
| 4 | Workflow engine: definitions, execution, retries, approval gates |
| 5 | Memory + knowledge: vector store, memories, summarization |
| 6 | Tool system + sandbox: file/git/search/test tools, container isolation |
| 7 | Autonomous development: developer agents producing code in a real repo |
| 8 | QA: review, test automation, bug-fix loops |
| 9 | Deployment: environments, CI/CD, migrations, rollback |
| 10 | Monitoring: metrics, alerts, incident handling |
| 11 | Advanced autonomy: learning, org memory, cross-project improvements |

See `32_DEVELOPMENT_PHASES.md`.

---

## 9. MVP Definition

See `33_MVP_SCOPE.md`. The MVP demonstrates:

```
Idea → Planning → Task generation → Agent assignment → Development → Testing → Review → Final result
```

- A single organization running a single simple software project (e.g., a CRUD web app).
- Orchestrator + minimal agents (PM, Architect, one Developer, one Reviewer, one QA).
- Task system, minimal workflow engine, one code sandbox, PostgreSQL state, no external
  deployment to cloud (local container deployment only).
- Autonomy level defaulting to **Level 2 (AI executes with approval)**.

---

## 10. Future Versions

| Version | Scope |
|---|---|
| v0 (MVP) | Single project, single org, local deployment, core agents |
| v1 | Full departmental agents, multi-env deployment, monitoring stack |
| v2 | Multi-project portfolios, org memory / learning, cost optimization |
| v3 | Parallel projects sharing infrastructure, advanced autonomy (L4) |
| v4 | Human oversight only (L5), adaptive self-tuning of prompts/policies within guardrails |

---

## 11. Major Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Agent executes destructive/insecure operations | High | Sandbox, least privilege, approval gates, deny-lists |
| Unbounded token/API costs | High | Budgets, routing, caching, limits (26) |
| Low-quality model output on novel patterns | Med | Review gates, multi-model routing, quality checks |
| Workflow deadlocks / infinite loops | Med | Timeouts, retry caps, watchdog (43) |
| Data exfiltration / prompt injection | High | Tool allow-lists, secrets policy, egress control (18, 39) |
| Repo drift / merge conflicts from parallel agents | Med | Task branches, serialization per file area, merge protocol (21) |
| Overwhelming human with approvals | Med | Risk-tiered approval policy (17) |
| Dependency/supply-chain attacks | High | Lockfiles, image pinning, dependency scanning (39) |
| Reset context loss / memory drift | Med | Memory summarization, state persistence (09) |

---

## 12. Technical Decisions (Locked in This Plan)

1. **Language:** Python 3.12 for the orchestration core.
2. **Agent framework:** lightweight, dependency-lean internal framework on top of a provider
   abstraction (OpenAI/Anthropic/Google + local via Ollama/vLLM). See `31_TECH_STACK.md`.
3. **Workflow engine:** internal lightweight engine (no heavy external BPM), modeled as
   directed graphs with typed steps. See `07_WORKFLOW_ENGINE.md`.
4. **Database:** PostgreSQL 16 (source of truth) + pgvector extension (embeddings).
5. **Message transport:** internal event bus via PostgreSQL (NOTIFY/LISTEN) or Redis,
   keeping the MVP dependency-lean; abstraction layer keeps it swappable.
6. **Sandboxing:** Docker containers per execution context with strict network/fs/limits.
7. **State:** persisted JSON + relational rows; git as source control for code artifacts.
8. **API:** REST + JSON for the control plane; WebSocket for streaming agent events.
9. **AuthN/Z:** project-local first (single organization/owner), OIDC-ready for future.

Decisions left open are listed in `50_OPEN_QUESTIONS.md`.

---

## 13. Success Criteria

1. An end-to-end run of the MVP pipeline succeeds on a greenfield CRUD app without
   manual code edits (human approves gates only).
2. ≥ 90% of tasks complete in first-pass review with zero critical security findings
   introduced.
3. All generated code passes configured test suites before merge.
4. Costs stay within configurable per-project budgets.
5. A second project can be bootstrapped from org templates without architectural rework.
6. Any failure is retried/escalated per policy and audited (no silent failures).

---

## 14. Open Questions

Tracked in `50_OPEN_QUESTIONS.md`. The most important:

- Q1: Which model providers are available at deployment time?
- Q2: What is the first real project the system will build (validates MVP)?
- Q3: Is multi-tenant hosting required from day one?
- Q4: Deployment targets for user products (local Docker vs cloud)?
- Q5: Regulatory constraints (SOC2, EU AI Act, data residency)?