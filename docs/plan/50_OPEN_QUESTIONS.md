# 50 — OPEN QUESTIONS

> Items that require a human decision before or during implementation. Do **not** silently
> assume answers. When answered, move the decision into the relevant doc and `PLANNING_STATUS`.

---

## Q1. Model Providers (blocking for Phase 2)
Which providers must work at deployment time? (OpenAI / Anthropic / Google / local via
Ollama / vLLM) and is a fallback chain required?
**Impact:** model registry config, adapter set, key provisioning.
**Default suggestion:** support OpenAI + Anthropic + Ollama(local), fallback chain
openai→anthropic→local.

## Q2. First real validation project
What is the first non-trivial project the system must autonomously build (to validate MVP)?
Recommend "task-management CRUD API (FastAPI + SQLite + JWT + tests + Dockerfile)" as the
least-ambiguity fixture.
**Impact:** fixtures, knowledge seed, acceptance criteria.

## Q3. Multi-tenancy from day one?
Single-org (single owner, API key) for MVP vs multi-org from the start?
**Default suggestion:** single-org MVP; multi-org in v1. Confirmed to avoid phase-1 schema
complexity?

## Q4. Deployment targets for user products
Local Docker Compose only (MVP) — or does the org need cloud targets (AWS/GCP) in v0 In
which case env creds provisioning required.
**Default:** local-only MVP.

## Q5. Data residency / regulations
Are there regulatory constraints (EU AI Act, SOC2, GDPR, data-residency regions) that change
privacy-profile routing or audit retention?
**Impact:** provider routing (private projects → local-only), retention settings.

## Q6. Frontend for humans
Console/CLI + REST/WS only for MVP, or is a minimal dashboard required early?
**Default:** no UI in MVP; heavy API-first.

## Q7. Model embedding provider
Which embedding model for memory/vector search at MVP (cloud vs local sentence-transformers)?
Privacy profile decides: private → local.
**Default:** local sentence-transformers (`all-MiniLM-L6-v2`) for MVP (zero cost, no keys).

## Q8. Git host for generated user code
Where do generated repos live? Bare remotes managed by the platform (default, local),
GitHub integration optional?
**Default:** platform-managed bare remotes in `./data/git/` MVP.

## Q9. Human approval channel
Email / webhook / API-poll only? Is Slack/Discord needed for notifications?
**Default:** API + optional email stub MVP; webhook adapter interface reserved.

## Q10. Sandbox network egress for package installs
MVP dev containers have **no egress**. Installing npm/pip packages needs either a local
package mirror/cache or allowlisted registry hosts. Confirm allowlist approach (registry
endpoints pip/npm) is acceptable.
**Default:** allowlist `files.pythonhosted.org`, `registry.npmjs.org` (mirror planned v1).

## Q11. Prompt & agent-def governance
Who may edit `config/agents/*.yaml` and `prompts/**` in production? Suggested: human admin
only (like infra). Confirm.

## Q12. Cost ceiling defaults
Default per-task cost ceiling and per-project budget (recommend $2/task, $250/model-call
avg project). Confirm or override.

## Q13. Max code task context size
Context budget defaults (we recommend prompt core 12k + task 60k tokens max by default).
Should large-file tasks be cap-limited more aggressively (e.g., 32k) for cost?

## Q14. Retrospective trigger
Should retrospectives run automatically at every project completion (could be costly) or on
flag only (budget/missteps observed)? Suggest: auto lightweight + on-flag deep.

## Q15. Concurrency default
Max concurrent agents per project default of 4 — acceptable? (Higher raises cost/lock
pressure.)

## Q16. Git identity for agent commits
Use a single platform identity ("AI-Agent-Bot <bot@...>") for all commits, or per-task
emails? Suggest single identity MVP (simple audit).

## Q17. Languages of first-party documents & prompts
English-only MVP? (Affects knowledge seeding and outputs.) Suggest English MVP.

## Q18. Semantic cache across projects
Enable cross-project semantic prompt caching (privacy concerns) — default OFF, confirm.

## Q19. Artifact storage retention
Confirm retention windows in `14_ARTIFACT_SYSTEM.md` (test reports 1y, code forever,
snapshots project-lifetime).

## Q20. Provider key quota per project
Separate per-project provider quotas vs org-pooled? Suggest org-pooled with per-project
budget ceilings (26). Confirm.