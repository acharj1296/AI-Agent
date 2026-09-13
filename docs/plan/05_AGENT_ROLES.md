# 05 — AGENT ROLES

Every agent is defined with the full contract template (see `04`, `35`, `36`). This document
provides the canonical role catalogue. MVP agent set is marked **[MVP]**.

**Legend for permissions:** T=Tools available; MEM=memory read/write; SPWN=may spawn
sub-agents (depth); APPR=approvals required; ESC=escalation targets.

---

## 1. Orchestrator — CEO **[MVP]**

- **ID:** `ceo_orchestrator`
- **Department:** Executive
- **Purpose:** Own the project pipeline and stage gates.
- **Responsibilities:** Decision on project stage, dispatch to managers, gate checks,
  approval routing, escalation resolution, portfolio (v2+) and project kickoff.
- **Inputs:** Project intake record, stage/event signals, approval decisions, escalated
  issues.
- **Outputs:** Stage transitions, workflow invocations, dispatch orders, decisions.
- **Tools:** read_project_state, read_artifacts, list_tasks, trigger_workflow, request_approval,
  escalate_to_human.
- **Permissions:** Highest of all agents, but never edits user code directly.
- **Memory:** R: org memory, project memory; W: project memory (decisions).
- **Spawn:** may spawn any agent at depth 1.
- **Fail conditions:** stage stuck, approvals ignored, escalation loop.
- **Escalation:** to Human Board for irreversible decisions.
- **Artifacts:** project_status, stage_decision records.

---

## 2. Product Department

### 2.1 Product Manager **[MVP]**
- **ID:** `pm_product_manager`
- **Purpose:** Turn research + intake into a PRD and roadmap.
- **Responsibilities:** Personas, journeys, MoSCoW prioritization, success metrics, roadmap,
  ticket generation approval.
- **Inputs:** intake, research artifacts, feasibility check.
- **Outputs:** PRD, user stories, acceptance criteria, roadmap, release plan.
- **Tools:** read/write artifacts, read project state, request_approval (PRD gate),
  create_tasks (as draft).
- **Memory:** R: all project memory; W: product memory.
- **Spawn:** none.
- **Approval:** PRD requires human approval before architecture begins (gate P5).
- **Artifacts:** `prd.md`, `user_stories.md`, `roadmap.md`.

### 2.2 Business Analyst
- **ID:** `ba_business_analyst`
- **Purpose:** Detailed requirement analysis and process modeling.
- **Responsibilities:** Requirement clarity, edge cases, data requirements, rule definitions.
- **Outputs:** requirement spec, use-case diagrams, data dictionary.
- **Spawn:** none.

### 2.3 Requirements Agent
- **ID:** `req_requirements`
- **Purpose:** Translate PRD/BA work into traceable requirements.
- **Outputs:** requirement items with IDs, acceptance criteria, traceability matrix.

---

## 3. Research Department

### 3.1 Market Research Agent
- **ID:** `research_market`
- **Purpose:** Market size, segments, trends, pricing.
- **Tools:** web_search, web_fetch **[sandbox-only, egress allowed]**.
- **Outputs:** market_report.md (sources cited).

### 3.2 Competitor Research Agent
- **ID:** `research_competitor`
- **Purpose:** Competition landscape, feature comparison, differentiation.
- **Outputs:** competitor_report.md.

### 3.3 Technical Research Agent
- **ID:** `research_technical`
- **Purpose:** Feasibility of technical approaches; library/pattern vetting.
- **Outputs:** tech_research_report.md, feasibility assessment.

> Research agents may **not** install software or run code beyond the sandbox browser/search
> tools. Their network egress is restricted to search/fetch APIs.

---

## 4. Architecture Department

### 4.1 System Architect
- **ID:** `arch_system` **[MVP]**
- **Purpose:** High-level system design from PRD.
- **Outputs:** system_architecture.md, C4 diagrams, ADR (architecture decision records).
- **Approval:** architecture gate P6 (human at L<4).

### 4.2 Database Architect
- **ID:** `arch_database`
- **Outputs:** schema.md + initial DDL migration, indexing plan.

### 4.3 Security Architect
- **ID:** `arch_security`
- **Outputs:** security_architecture.md (authN/Z, secrets, threat model pointer).
- **Approval:** security review gate before production.

### 4.4 DevOps Architect
- **ID:** `arch_devops`
- **Outputs:** deployment_architecture.md, CI/CD design, environment layout.

---

## 5. Development Department

All developers share tools: read_file, write_file, list_dir, run_terminal, git_commit,
run_tests, read_repo. **Network: none by default** (dependency fetch only via locked
mirror/registry). **Secrets: none.**

### 5.1 Backend Developer **[MVP]** — `dev_backend`
Backend features, business logic, services. Handles structured-output code tasks.

### 5.2 Frontend Developer — `dev_frontend`
UI components, pages, wiring to API. Egress: none. Runs `npm run build` in sandbox.

### 5.3 Database Developer — `dev_database`
Migrations, queries, indexes, seed data. Uses `run_terminal` for `psql`/migration tools.

### 5.4 API Developer — `dev_api`
API contracts, OpenAPI specs, endpoint implementations, validation.

### 5.5 Integration Developer — `dev_integration`
Third-party integrations, webhooks, message payloads. Egress: allowed only to whitelisted
hosts for integration testing.

---

## 6. Quality Department

### 6.1 QA Agent **[MVP]** — `qa_lead`
Test plan authoring, coverage mapping to requirements; coordinates fix loop.

### 6.2 Test Automation Agent **[MVP]** — `qa_test_automation`
Writes unit/integration/E2E tests; runs test suites; formats results.
**Tools additionally:** run_tests, read_repo, write_tests.

### 6.3 Code Review Agent **[MVP]** — `qa_code_reviewer`
Reviews diffs for correctness, style, security, performance; produces structured review
(found/severity/suggestions); decides APPROVE / REQUEST_CHANGES.

### 6.4 Security Testing Agent — `qa_security_tester`
Runs SAST (e.g., bandit/semgrep), dependency audit, secret scanning; produces findings list.

### 6.5 Performance Testing Agent — `qa_perf_tester`
Load profiles, benchmarks; reports latency/throughput vs NFR targets.

---

## 7. DevOps Department

### 7.1 CI/CD Agent — `devops_cicd`
Builds pipeline definitions (GitHub Actions or equivalent), runs builds in sandbox.

### 7.2 Deployment Agent — `devops_deploy`
Performs deploys (local Docker MVP), runs migrations, health checks.
**Approval:** production deploy requires human (always).

### 7.3 Infrastructure Agent — `devops_infra`
Writes Docker/compose/terraform configs; manages the sandbox resources.

### 7.4 Monitoring Agent — `devops_monitor`
Configures health checks, log/metrics dashboards, alert rules for deployed apps.

---

## 8. Management

### 8.1 Project Manager (`mgmt_pm`) **[MVP]**
Schedules milestones, tracks dependency chains, detects slippage, produces status reports.

### 8.2 Progress Manager (`mgmt_progress`)
Monitors task completion velocity, flag blocked tasks, replan.

### 8.3 Decision/Approval Agent (`mgmt_decision`)
Evaluates conflict resolution options (with decision framework `44`), prepares approval
packets for the human board with impact summaries. **Cannot approve on its own for
high-risk items.**

---

## 9. Agent Role Matrix (all agents)

| Agent | Tools (group) | Mem R/W | Spawn | Approvals | Escalates to |
|---|---|---|---|---|---|
| ceo_orchestrator | state/events/approval | P,R | yes(d1) | — | Human Board |
| pm_product_manager | artifacts/tasks | P | no | PRD gate | Orchestrator |
| ba_business_analyst | artifacts | P | no | — | PM |
| req_requirements | artifacts | P | no | — | PM |
| research_market | web | P,R | no | — | PM |
| research_competitor | web | P,R | no | — | PM |
| research_technical | web | P,R | no | — | PM |
| arch_system | artifacts | P | no | architecture gate | Orchestrator |
| arch_database | artifacts/migr | P | no | — | arch_system |
| arch_security | artifacts/code(read) | P | no | security gate | Orchestrator |
| arch_devops | artifacts/infra(read) | P | no | — | arch_system |
| dev_backend | repo/term/tests | T | no | — | QA reviewer → PM |
| dev_frontend | repo/term/build | T | no | — | QA reviewer → PM |
| dev_database | repo/term/migr | T | no | — | QA reviewer → PM |
| dev_api | repo/term | T | no | — | QA reviewer → PM |
| dev_integration | repo/term | T | no | — | QA reviewer → PM |
| qa_lead | artifacts | P,R | no | — | PM |
| qa_test_automation | repo/term/tests | T | no | — | qa_lead |
| qa_code_reviewer | repo(read) | T,R | no | — | PM, orchestrator |
| qa_security_tester | repo(read)/security tools | R | no | findings gate | orchestrator |
| qa_perf_tester | repo(read)/load tools | R | no | findings gate | qa_lead |
| devops_cicd | infra/term | P,R | no | — | orchestrator |
| devops_deploy | infra/term/deploy | P,R | no | prod-deploy gate (always) | orchestrator |
| devops_infra | infra/term | P,R | no | — | orchestrator |
| devops_monitor | infra/mon | P,R | no | — | orchestrator |
| mgmt_pm | tasks/artifacts | P,R | no | — | orchestrator |
| mgmt_progress | tasks | P,R | no | — | mgmt_pm |
| mgmt_decision | all read | P,R | no | — | Human Board |

*(P = project memory, R = research/learnings, T = task memory)*