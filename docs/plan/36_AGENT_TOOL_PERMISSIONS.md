# 36 — AGENT TOOL PERMISSIONS

---

## 1. Permission Model

- Each agent def has a `permissions` block: allowed tool ids, path scopes, egress policy,
  secret access (default none).
- The **Permission Guard** is the only enforcement point (see `11` §3, `18` §3).
- Default-deny: any tool not explicitly granted is denied.

### Permission keys per agent
| Key | Meaning |
|---|---|
| `tools | name | rw: [read,write,exec]` | tool + allowed mode |
| `paths` | allowed read/write roots (workspace) |
| `egress` | none / allowlist / localhost |
| `secrets` | [ ] or explicit secret ids |
| `spawn` | allowed child agent ids (oracle only) |
| `sudo`/`privileged` | always false |

---

## 2. Permission Matrix (source of truth)

Tools key:
- R = read-only; W = write; X = exec; D = deploy.

| Agent | read_file | write_file | list_dir | run_terminal | git_commit | run_tests | web_search | web_fetch | deploy_target | db_migrate | sast_scan | dep_audit | exec_python |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ceo_orchestrator | R | — | R | — | — | — | — | — | — | — | — | — | — |
| pm_product_manager | R | W | R | — | — | — | — | — | — | — | — | — | — |
| ba_business_analyst | R | W | R | — | — | — | — | — | — | — | — | — | — |
| req_requirements | R | W | R | — | — | — | — | — | — | — | — | — | — |
| research_market | R | W | R | — | — | — | X(allowlist) | X(allowlist,80/443) | — | — | — | — | — |
| research_competitor | R | W | R | — | — | — | X(allowlist) | X(allowlist,80/443) | — | — | — | — | — |
| research_technical | R | W | R | — | — | — | X(allowlist) | X(allowlist,80/443) | — | — | — | — | — |
| arch_system | R | W | R | — | — | — | — | — | — | — | — | — | — |
| arch_database | R | W | R | — | — | — | — | — | — | X | — | — | — |
| arch_security | R | W | R | — | — | — | — | — | — | — | R | R | — |
| arch_devops | R | W | R | — | — | — | — | — | — | R | — | — | — |
| dev_backend | R | W | R | X | X | X | — | — | — | — | — | — | — |
| dev_frontend | R | W | R | X | X | X | — | — | — | — | — | — | — |
| dev_database | R | W | R | X | X | X | — | — | — | X | — | — | — |
| dev_api | R | W | R | X | X | X | — | — | — | — | — | — | X |
| dev_integration | R | W | R | X | X | X | — | — | — | — | — | — | X |
| qa_lead | R | W | R | — | — | — | — | — | — | — | — | — | — |
| qa_test_automation | R | W | R | X | — | X | — | — | — | — | — | — | X |
| qa_code_reviewer | R | — | R | — | — | — | — | — | — | — | — | — | — |
| qa_security_tester | R | W(report) | R | X(non-mutating scans) | — | — | — | — | — | — | X | X | X |
| qa_perf_tester | R | W(report) | R | X | — | — | — | — | — | — | — | — | X |
| devops_cicd | R | W | R | X | X(branch-push only) | X | — | — | — | — | — | — | — |
| devops_deploy | R | W | R | X | — | — | — | — | D(staging/allow) | X(migrate) | — | — | — |
| devops_infra | R | W | R | X | X | — | — | — | — | — | — | — | — |
| devops_monitor | R | W(config) | R | X | — | — | — | — | — | — | — | — | — |
| mgmt_pm | R | W | R | — | — | — | — | — | — | — | — | — | — |
| mgmt_progress | R | W | R | — | — | — | — | — | — | — | — | — | — |
| mgmt_decision | R(all by packet) | W(packet) | R | — | — | — | — | — | — | — | — | — | — |

---

## 3. Path Scopes

| Role | read root | write root |
|---|---|---|
| Product/Research/Arch | project artifacts (`artifacts/`) | artifacts |
| Developer | `/workspace` (whole repo read) | `/workspace/` only; write_scope from task |
| QA (automation) | repo read + tests | `/workspace/tests` + reports |
| Reviewers | repo read | none (reports → artifact) |
| DevOps | repo read + infra dirs | `deploy/`, workflows, image files |
| Deploy | env config | only current env dir |

---

## 4. Egress Policy

| Agent | egress |
|---|---|
| all developers | none |
| research agents | allowlist: configured search API hosts + fetch-allow FQDN list |
| qa | none (except test-triggered calls inside test environment localhost) |
| devops | registry hosts (pip/npm), localhost stack |
| dev_integration | allowlist of integration host configured per project |

---

## 5. Secret Access

Only tasks carrying an explicit `secret_allow: [secret_names]` may cause secrets to be
injected into sandbox env. Agent def `secrets` list gates which names it may request.
Default for all agents: none.

---

## 6. Verification

- Permission config is schema-validated at startup and on change (fail-closed).
- A `permission_report` is generated per project showing effective matrix — human viewable.