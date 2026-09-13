# PLAN INDEX

Complete index of the AI-Agent Company planning system. All documents live in `docs/plan/`.

---

## Reading Order

**Track A — Why & What (start here)**
1. `00_MASTER_PLAN.md` — overview, boundaries, decisions, risks
2. `01_VISION.md` — vision and tiers of autonomy
3. `02_REQUIREMENTS.md` — functional + non-functional requirements

**Track B — The System (architecture)**

| # | Doc | Purpose |
|---|---|---|
| 03 | SYSTEM_ARCHITECTURE | module/component breakdown, deployment topology |
| 04 | AGENT_ARCHITECTURE | agent definition model, hierarchy, delegation, communication rules |
| 05 | AGENT_ROLES | full role catalogue (28 agents), capability matrix |
| 06 | AGENT_LIFECYCLE | run state machine, retries, spawning, memory injection |
| 07 | WORKFLOW_ENGINE | declarative workflows, step types, gates, retries, examples |
| 08 | TASK_SYSTEM | task entity, state machine, queue, dependencies, file locks |
| 09 | MEMORY_SYSTEM | memory layers, storage, retrieval, summarization, cleanup |
| 10 | KNOWLEDGE_SYSTEM | templates, playbooks, standards, lessons, registry |
| 11 | TOOL_SYSTEM | tool contracts, catalogue, permission guard, risks |
| 12 | MODEL_ROUTING | provider abstraction, model selection, fallback, cost |
| 13 | PROJECT_STATE | single source of truth, invariants, snapshots |
| 14 | ARTIFACT_SYSTEM | versioned deliverables, provenance, retention |
| 15 | COMMUNICATION_PROTOCOL | mediated channels, info-request protocol, trust |
| 16 | EVENT_SYSTEM | event taxonomy, delivery, outbox, replay |
| 17 | HUMAN_APPROVAL | tiers, packets, UX, level gating |
| 18 | SECURITY | boundaries, permissions, secrets, injection defenses |
| 19 | SANDBOXING | isolation, limits, network/fs policy, lifecycle |
| 20 | CODE_EXECUTION | build/test/run flows, environments, contracts |
| 21 | TESTING_SYSTEM | test layers, pipeline, failure→debug loop, coverage |
| 22 | CODE_REVIEW | review workflow, rubric, findings, merge protocol |
| 23 | DEPLOYMENT | environments, pipeline, rollback, migrations |
| 24 | MONITORING | platform + app monitoring, alerting, logs/tracing |
| 25 | ERROR_RECOVERY | failure categories, retries, escalation, recovery |
| 26 | COST_CONTROL | budgets, routing-for-cost, caching, safeguards |
| 27 | OBSERVABILITY | logs/metrics/traces/audit conventions |
| 28 | DATABASE_DESIGN | entity model, tables, indexes, ownership |
| 29 | API_DESIGN | REST/WS surface, envelopes, auth |
| 30 | FOLDER_STRUCTURE | repo layout, module dependency rules |

**Track C — Delivery (later reading)**

| # | Doc | Purpose |
|---|---|---|
| 31 | TECH_STACK | technology choices + rationale |
| 32 | DEVELOPMENT_PHASES | Phase 0–11 scope, tasks, exit criteria |
| 33 | MVP_SCOPE | smallest useful autonomous build system |
| 34 | FUTURE_ROADMAP | v0.1 → v3.0 |
| 35 | AGENT_PROMPTS | mandatory prompt template, guardrails, examples |
| 36 | AGENT_TOOL_PERMISSIONS | the permission matrix (source of truth) |
| 37 | AGENT_STATE_MACHINE | canonical run states, guards, events |
| 38 | PROJECT_PIPELINE | stage-by-stage spec, gates, artifacts |
| 39 | SECURITY_THREAT_MODEL | STRIDE per trust boundary |
| 40 | TEST_STRATEGY | platform test layers, coverage, CI gates |
| 41 | DEPLOYMENT_STRATEGY | deployable units, environments, playbook |
| 42 | SCALABILITY | limits, growth paths, bottlenecks |
| 43 | FAILURE_SCENARIOS | enumerated scenarios + responses |
| 44 | DECISION_FRAMEWORK | decision packets, reversal authority, escalation |
| 45 | AUTONOMY_LEVELS | L0–L5 definitions and approval mapping |
| 46 | HUMAN_IN_THE_LOOP | touchpoints, UX, SLA, overrides |
| 47 | DATA_FLOW | primary flows, state ownership, principles |
| 48 | SEQUENCE_FLOWS | end-to-end simulation + sequence diagrams |
| 49 | IMPLEMENTATION_CHECKLIST | actionable phase-by-phase checklist |
| 50 | OPEN_QUESTIONS | decisions pending human input |

**Track D — Meta**
- `PLAN_INDEX.md` (this file)
- `PLANNING_STATUS.md`

---

## Document Dependencies (who needs whom)

| Doc | Depends on |
|---|---|
| 00 | all (master references) |
| 02 | 01 |
| 03 | 02, 30 |
| 04 | 03, 36 |
| 05 | 04, 36 |
| 06 | 04, 12, 09, 37 |
| 07 | 03, 08, 17 |
| 08 | 21 (file-lock overlap), 37 |
| 09 | 12 (embeddings), 28 (tables) |
| 10 | 09, 14 |
| 11 | 19, 36, 18 |
| 12 | 26, 27, 31 |
| 13 | 28 |
| 14 | 28, 11 (access) |
| 15 | 16, 13, 14 |
| 16 | 28 (event tables) |
| 17 | 45, 46, 44 |
| 18 | 39, 36, 19 |
| 19 | 18, 20 |
| 20 | 19, 21 |
| 21 | 08, 22, 26 |
| 22 | 08, 21, 18 |
| 23 | 21, 22, 41, 17 |
| 24 | 27, 23 |
| 25 | 06, 08, 07, 44 |
| 26 | 12, 27, 28 |
| 27 | 16, 28 |
| 28 | 30 |
| 29 | 03, 28 |
| 30 | 03 |
| 31 | 12, 28, 19, 30 |
| 32 | 31, 33 |
| 33 | 00, 32 |
| 34 | 33 |
| 35 | 04, 36, 45 |
| 36 | 04, 11, 18 |
| 37 | 06 |
| 38 | 03, 07, 17, 05 |
| 39 | 18, 36 |
| 40 | 30, 31 |
| 41 | 23, 31 |
| 42 | 03, 31, 16 |
| 43 | 25, 18, 44 |
| 44 | 45, 43 |
| 45 | 17, 46 |
| 46 | 17, 45 |
| 47 | 13, 14, 16, 28 |
| 48 | 38, 07, 21, 22, 23 |
| 49 | 32 (all phases) |
| 50 | everything (resulting decisions) |

---

## MVP-Related Documents (must agree)

- `33_MVP_SCOPE.md` (primary)
- `32_DEVELOPMENT_PHASES.md` (Phases 0–7 = MVP)
- `31_TECH_STACK.md`
- `49_IMPLEMENTATION_CHECKLIST.md` (Phases 0–7)
- `36_AGENT_TOOL_PERMISSIONS.md` (MVP agent subset marked in `05`)
- `40_TEST_STRATEGY.md` (platform gates)

## Future-Architecture Documents (v1+)

- `34_FUTURE_ROADMAP.md`
- `42_SCALABILITY.md`
- `41_DEPLOYMENT_STRATEGY.md` (staging/prod)
- `39_SECURITY_THREAT_MODEL.md` (v1 hardening)
- `46_HUMAN_IN_THE_LOOP.md` (dashboard-era UX)

---

## Implementation Order (post-planning)

1. Resolve blocking open questions (`50`: Q1, Q4, Q8, Q10).
2. Phase 0 close-out → commit plan.
3. Phase 1 (infra) → Phase 7 (autonomous dev) → MVP acceptance (`33` §5).
4. Phase 8–11 per `32`.

Each phase must pass its exit criteria in `32` and checklist rows in `49`.