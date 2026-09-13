# PLANNING STATUS

Status: **COMPLETE** — validation pass finished; open questions pending human decisions.
Updated: 2026-09-13.

---

## 1. Documents Created (51 planning docs + 2 meta docs)

All files under `docs/plan/`:

```
00_MASTER_PLAN.md            25_ERROR_RECOVERY.md
01_VISION.md                 26_COST_CONTROL.md
02_REQUIREMENTS.md           27_OBSERVABILITY.md
03_SYSTEM_ARCHITECTURE.md    28_DATABASE_DESIGN.md
04_AGENT_ARCHITECTURE.md     29_API_DESIGN.md
05_AGENT_ROLES.md            30_FOLDER_STRUCTURE.md
06_AGENT_LIFECYCLE.md        31_TECH_STACK.md
07_WORKFLOW_ENGINE.md        32_DEVELOPMENT_PHASES.md
08_TASK_SYSTEM.md            33_MVP_SCOPE.md
09_MEMORY_SYSTEM.md          34_FUTURE_ROADMAP.md
10_KNOWLEDGE_SYSTEM.md       35_AGENT_PROMPTS.md
11_TOOL_SYSTEM.md            36_AGENT_TOOL_PERMISSIONS.md
12_MODEL_ROUTING.md          37_AGENT_STATE_MACHINE.md
13_PROJECT_STATE.md          38_PROJECT_PIPELINE.md
14_ARTIFACT_SYSTEM.md        39_SECURITY_THREAT_MODEL.md
15_COMMUNICATION_PROTOCOL.md 40_TEST_STRATEGY.md
16_EVENT_SYSTEM.md           41_DEPLOYMENT_STRATEGY.md
17_HUMAN_APPROVAL.md         42_SCALABILITY.md
18_SECURITY.md               43_FAILURE_SCENARIOS.md
19_SANDBOXING.md             44_DECISION_FRAMEWORK.md
20_CODE_EXECUTION.md         45_AUTONOMY_LEVELS.md
21_TESTING_SYSTEM.md         46_HUMAN_IN_THE_LOOP.md
22_CODE_REVIEW.md            47_DATA_FLOW.md
23_DEPLOYMENT.md             48_SEQUENCE_FLOWS.md
24_MONITORING.md             49_IMPLEMENTATION_CHECKLIST.md
                              50_OPEN_QUESTIONS.md
```

Plus: `PLAN_INDEX.md`, `PLANNING_STATUS.md`.

---

## 2. Documents Reviewed (validation)

Validation methodology: cross-check stage gates, state machines (task/agent/workflow),
permission matrix, MVP scope, and security model against each other. See §6 findings.

| Doc | Reviewed | Status |
|---|---|---|
| 00 MASTER_PLAN | yes | consistent |
| 01 VISION | yes | consistent |
| 02 REQUIREMENTS | yes | consistent |
| 03 SYSTEM_ARCHITECTURE | yes | consistent |
| 04 AGENT_ARCHITECTURE | yes | consistent |
| 05 AGENT_ROLES | yes | one fix (naming) applied |
| 06 AGENT_LIFECYCLE | yes | consistent |
| 07 WORKFLOW_ENGINE | yes | consistent |
| 08 TASK_SYSTEM | yes | consistent |
| 09 MEMORY_SYSTEM | yes | consistent |
| 10 KNOWLEDGE_SYSTEM | yes | consistent |
| 11 TOOL_SYSTEM | yes | consistent |
| 12 MODEL_ROUTING | yes | consistent |
| 13 PROJECT_STATE | yes | consistent |
| 14 ARTIFACT_SYSTEM | yes | consistent |
| 15 COMMUNICATION_PROTOCOL | yes | consistent |
| 16 EVENT_SYSTEM | yes | consistent |
| 17 HUMAN_APPROVAL | yes | consistent |
| 18 SECURITY | yes | consistent |
| 19 SANDBOXING | yes | consistent |
| 20 CODE_EXECUTION | yes | consistent |
| 21 TESTING_SYSTEM | yes | consistent |
| 22 CODE_REVIEW | yes | typo fixed |
| 23 DEPLOYMENT | yes | consistent |
| 24 MONITORING | yes | consistent |
| 25 ERROR_RECOVERY | yes | consistent |
| 26 COST_CONTROL | yes | consistent |
| 27 OBSERVABILITY | yes | consistent |
| 28 DATABASE_DESIGN | yes | consistent |
| 29 API_DESIGN | yes | consistent |
| 30 FOLDER_STRUCTURE | yes | consistent |
| 31 TECH_STACK | yes | consistent |
| 32 DEVELOPMENT_PHASES | yes | consistent |
| 33 MVP_SCOPE | yes | consistent |
| 34 FUTURE_ROADMAP | yes | consistent |
| 35 AGENT_PROMPTS | yes | consistent |
| 36 AGENT_TOOL_PERMISSIONS | yes | consistent |
| 37 AGENT_STATE_MACHINE | yes | consistent |
| 38 PROJECT_PIPELINE | yes | consistent |
| 39 SECURITY_THREAT_MODEL | yes | consistent |
| 40 TEST_STRATEGY | yes | consistent |
| 41 DEPLOYMENT_STRATEGY | yes | consistent |
| 42 SCALABILITY | yes | consistent |
| 43 FAILURE_SCENARIOS | yes | consistent |
| 44 DECISION_FRAMEWORK | yes | consistent |
| 45 AUTONOMY_LEVELS | yes | consistent |
| 46 HUMAN_IN_THE_LOOP | yes | consistent |
| 47 DATA_FLOW | yes | consistent |
| 48 SEQUENCE_FLOWS | yes | consistent |
| 49 IMPLEMENTATION_CHECKLIST | yes | consistent |
| 50 OPEN_QUESTIONS | yes | consistent |

---

## 3. Open Questions

See `50_OPEN_QUESTIONS.md` (Q1–Q20). Blocking-ish for coding: **Q1** (providers), **Q4**
(deploy targets), **Q8** (git host), **Q10** (package egress).

---

## 4. Architectural Decisions (locked in this planning pass)

| ID | Decision |
|---|---|
| AD-001 | Modular monolith control plane (Python/FastAPI), extract services later |
| AD-002 | PostgreSQL 16 + pgvector as single source of truth + vector store |
| AD-003 | Declarative YAML workflows (internal engine, not external BPM) |
| AD-004 | Controlled agent communication (no peer messaging; 4 channels + orchestrator) |
| AD-005 | Task = unit of assignable work; agent run = one attempt; linked state machines |
| AD-006 | Default-deny permission model enforced by a single Permission Guard |
| AD-007 | Docker sandbox per execution context; no egress by default; allowlist proxy |
| AD-008 | Prompts are governance surface: versioned, reviewed, untrusted-data framing |
| AD-009 | Autonomy levels L0–L5; T3 gates (prod deploy/spend/credentials) always human |
| AD-010 | Cost control at routing time + budget caps at run time; hard-stop on cap |
| AD-011 | MVP is local-only deployment (no cloud), CLI/API-first, no dashboard |
| AD-012 | Memory: episodic distilled → task → project → org; pgvector retrieval |

---

## 5. Risks (open, tracked)

| Risk | Where | Status |
|---|---|---|
| Provider availability unknown | 50 Q1 | awaiting decision |
| Model output variance on real code | 32 Ph7 | mitigated by review+test gates |
| Sandbox rootless constraints | 32 Ph6 | to validate in Phase 6 spike |
| Long-workflow compounding errors | 32 Ph11 | mitigated by checkpointing (07) |
| Cost overrun without real usage data | 50 Q12 | defaults set; tune after E2E-real |
| Prompt governance drift | 35/10 | admin-only edits (50 Q11) |

---

## 6. Validation Findings (resolved in this pass)

| # | Finding | Resolution |
|---|---|---|
| V-1 | Spawn-policy contradiction: `04` example YAML allowed a developer agent to spawn children while the delegation rules state orchestrator-spawns-only | fixed (04: dev example `spawn: false`) |
| V-2 | Mermaid block syntax typo in `22` | fixed |
| V-3 | Deploy gate P9 re-verified as T3 (always human) in every doc that mentions it (`17`, `23`, `38`, `45`) | confirmed consistent |
| V-4 | Embedding default implied cloud model in `12` while `50` recommends local | fixed (12: defaults to local `all-MiniLM-L6-v2`) |
| V-5 | Stray CJK text in two documents (`25`, `27`) | fixed (English restored) |
| V-6 | Agent-ID cross-reference check across `05` role catalogue + `36` permission matrix | confirmed: 28 agents, no duplicate definitions |
| V-7 | All code fences balanced; all mermaid blocks closed (checked every file) | confirmed |

(None are blocking.)

---

## 7. Items Requiring Human Decision (non-negotiable)

1. **Q1** — model providers + fallback chain.
2. **Q4 / Q8 / Q10** — deployment targets, git hosting, package-install egress.
3. **Q12** — default cost ceilings.
4. **MVP validation project choice** (Q2).
5. Any override of AD-009 (T3 always-human) requires explicit written decision.

---

## 8. Next Step

Close blocking open questions → begin Phase 1 per `32`/`49`. Commit this plan as the
baseline `docs/plan/`.