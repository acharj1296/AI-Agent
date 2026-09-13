# 02 — REQUIREMENTS

---

## 1. Functional Requirements

### 1.1 Project Intake
- F-INTAKE-01: System accepts a project idea via API or UI (text, optional voice).
- F-INTAKE-02: System generates a structured intake record (problem statement, target user,
  rough scope, constraints, success criteria).
- F-INTAKE-03: System asks clarifying questions when input is ambiguous or incomplete.
- F-INTAKE-04: System validates that at least one solvable problem exists before advancing.

### 1.2 Research
- F-RESEARCH-01: System can perform web searches and extract source URLs and summaries.
- F-RESEARCH-02: System performs market research (TAM/SAM/SOM estimation, target audience).
- F-RESEARCH-03: System performs competitor research (existing solutions, differentiation).
- F-RESEARCH-04: System performs technical research (libraries, patterns, feasibility).
- F-RESEARCH-05: Research outputs are persisted as versioned artifacts with sources cited.

### 1.3 Validation
- F-VALIDATE-01: System produces a feasibility assessment (technical, cost, timeline).
- F-VALIDATE-02: System identifies critical risks and open blockers.
- F-VALIDATE-03: System recommends proceeding, pivoting, or aborting with justification.

### 1.4 Specification (PRD)
- F-PRD-01: System produces a Product Requirements Document covering:
  - Problem statement
  - Target users (personas)
  - Core user journeys
  - Functional requirements (prioritized: MoSCoW)
  - Non-functional requirements (performance, security, accessibility, scalability)
  - Success metrics
  - Constraints
- F-PRD-02: PRD is versioned and stored as an artifact.
- F-PRD-03: System produces user stories with acceptance criteria from PRD.

### 1.5 Architecture
- F-ARCH-01: System produces a system architecture document (components, interactions, data flow).
- F-ARCH-02: System produces a database design (schema, migrations, indexing strategy).
- F-ARCH-03: System produces a security architecture (auth, secrets, threat model).
- F-ARCH-04: System produces a deployment architecture (environments, infrastructure).
- F-ARCH-05: System produces a technology selection document with rationale.

### 1.6 Planning
- F-PLAN-01: System decomposes the project into milestones.
- F-PLAN-02: System decomposes milestones into epics and tasks.
- F-PLAN-03: System identifies task dependencies.
- F-PLAN-04: System estimates task complexity/duration.
- F-PLAN-05: System produces a development roadmap.

### 1.7 Development
- F-DEV-01: System initializes a git repository for the user project.
- F-DEV-02: Agents can create/modify files in the project repo.
- F-DEV-03: Agents can run shell commands inside a sandboxed environment.
- F-DEV-04: System follows a branch strategy (feature branches).
- F-DEV-05: Commits are atomic and well-described.
- F-DEV-06: System can install dependencies, build, and run the application locally.

### 1.8 Quality
- F-QA-01: System generates unit tests for new code.
- F-QA-02: System generates integration tests where applicable.
- F-QA-03: System runs all tests automatically after code generation.
- F-QA-04: Failed tests automatically trigger debugging/fixing tasks.
- F-QA-05: System performs automated code review for style, correctness, and security.

### 1.9 Security
- F-SEC-01: System runs static analysis (SAST) on generated code.
- F-SEC-02: System checks for known vulnerabilities in dependencies.
- F-SEC-03: System enforces secrets not embedded in source code.
- F-SEC-04: Security findings are captured as tasks and fed back into development.

### 1.10 Deployment
- F-DEPLOY-01: System can deploy to local container (MVP).
- F-DEPLOY-02: System can deploy to cloud environments (v1).
- F-DEPLOY-03: System supports multi-environment deployment (dev/staging/prod).
- F-DEPLOY-04: System supports rollback on failed deployment.

### 1.11 Monitoring & Maintenance
- F-MON-01: System generates basic monitoring configuration for deployed apps.
- F-MON-02: System can detect runtime errors and create maintenance tasks.
- F-MON-03: System can iterate on feature requests and bug reports post-launch.

### 1.12 Orchestration
- F-ORCH-01: Orchestrator manages project stage transitions.
- F-ORCH-02: Orchestrator dispatches tasks to appropriate agents.
- F-ORCH-03: Orchestrator enforces approval gates.
- F-ORCH-04: Orchestrator handles agent failures and retries.
- F-ORCH-05: Orchestrator tracks project state across all dimensions.

### 1.13 Human-in-the-Loop
- F-HITL-01: Autonomy level is configurable per organization and per project.
- F-HITL-02: Certain operations always require approval regardless of level (production deploy, spend).
- F-HITL-03: Humans can view, approve, reject, or modify any artifact or decision.
- F-HITL-04: Humans can pause, resume, or cancel any running workflow.

### 1.14 Observability
- F-OBS-01: System logs all agent actions with timestamps and context.
- F-OBS-02: System tracks token usage per agent, per task, per project.
- F-OBS-03: System tracks cost per project and per agent.
- F-OBS-04: System provides a dashboard (API-first) to view status, costs, and artifacts.

### 1.15 Memory & Learning
- F-MEM-01: Agents maintain short-term memory (within a single run).
- F-MEM-02: Agents maintain long-term memory across runs within a project.
- F-MEM-03: Organization-wide memory across projects.
- F-MEM-04: Post-project retrospectives are stored for learning.

---

## 2. Non-Functional Requirements

### 2.1 Performance
- NFR-PERF-01: Orchestrator processes a new stage transition within 5 seconds.
- NFR-PERF-02: Agent spawn completes within 10 seconds.
- NFR-PERF-03: Task queue processes 100 tasks/minute at steady state.
- NFR-PERF-04: System supports at least 5 concurrent projects in v1.

### 2.2 Reliability
- NFR-REL-01: No silent failures; every failure is logged and retried or escalated.
- NFR-REL-02: Workflow state is persisted and recoverable after system restart.
- NFR-REL-03: Agent runs are idempotent where possible.
- NFR-REL-04: System survives single-component failure (no single point of failure for state).

### 2.3 Security
- NFR-SEC-01: Secrets are never stored in logs, artifacts, or source code.
- NFR-SEC-02: All inter-agent communication is authenticated and authorized.
- NFR-SEC-03: Code execution is fully sandboxed with no host escape possible.
- NFR-SEC-04: Audit logs are immutable and retained for configurable period.
- NFR-SEC-05: API keys are encrypted at rest.

### 2.4 Scalability
- NFR-SCALE-01: Horizontal scaling of agent workers.
- NFR-SCALE-02: Database supports concurrent project isolation.
- NFR-SCALE-03: Artifact storage scales independently from metadata.

### 2.5 Cost Control
- NFR-COST-01: Token budget per task, per agent, per project, and per organization.
- NFR-COST-02: Alerts at configurable cost thresholds (warn/hard stop).
- NFR-COST-03: Model routing optimizes cost vs quality per task.

### 2.6 Usability
- NFR-USE-01: API-first design; human-facing UI is a consumer of the API.
- NFR-USE-02: Project state is inspectable at every stage.
- NFR-USE-03: At least 80% of operations can be triggered via CLI.

### 2.7 Maintainability
- NFR-MAINT-01: Agents are defined via configuration + prompts, not hardcoded behavior.
- NFR-MAINT-02: Tools are registered via a plugin system.
- NFR-MAINT-03: Workflow definitions are declarative (YAML or equivalent).

---

## 3. Constraints

- MVP must run on a single machine with Docker.
- MVP must use PostgreSQL (local Docker) as primary store.
- MVP must not depend on external orchestration services (e.g., Temporal, Airflow).
- Total MVP dependencies must be auditable.
- No cloud account required for MVP (local-only deployment of user projects).