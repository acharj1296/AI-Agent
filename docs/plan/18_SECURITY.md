# 18 — SECURITY

---

## 1. Security Objectives

1. Protect the control plane and its data.
2. Protect user projects & secrets from agent actions.
3. Prevent prompt/tool injection from steering the org maliciously.
4. Prevent data exfiltration from both sandboxes and the control plane.
5. Provide an auditable trail of every privileged action.

---

## 2. Security Boundaries

```
[Human] ──API── [Control Plane] ──sandbox proxy── [Sandbox containers]
                    │                                  │
           [DB/object store]                    [network-mesh (no egress by default)]
```

- **Boundary A (Human→System):** authn/authz for commands; approval decisions are the
  least-privilege path to mutation.
- **Boundary B (Control Plane→Sandbox):** sandbox runs with restricted capabilities; the
  control plane only exposes the guarded tool API (see `11`).
- **Boundary C (Sandbox→Network):** egress policy per agent/tool (default **none**); egress
  via explicit allow-listed endpoints through the egress proxy (MVP: no egress except
  research/registry hosts).
- **Boundary D (Sandbox→Host Filesystem):** bind-mounts limited to workspace + temp workdir
  per project; read-only system mounts.

---

## 3. Agent Permissions Model

- **Role-Based:** every agent = a role with a permission set (tools + scope).
- **Scope model:** `(action, resource)`. Examples:
  - `dev_backend`: `{write: /workspace, run: read-write shell within sandbox}`
  - `research_market`: `{web: allowlist}`
  - `devops_deploy`: `{deploy: env=staging}` (never prod auth in sandbox)
- **Secrets:** agents never see secrets; tools inject secret references to sandbox only when
  a task is explicitly authorized (secret_allow flag in task).

---

## 4. Secret Management

- Secret store (MVP: local encrypted `.env`-backed vault; v1: HashiCorp Vault or cloud KMS).
- Secrets are referenced by ID; values never appear in events, logs, prompts, or artifacts.
- Rotation policy & generation for sandbox pod identities.
- Logs scrub detector (regex heuristics + secret-shape scan) as a last-resort guard.

---

## 5. API Key Protection

- Providers' API keys stored encrypted at rest; decrypted only inside the model client
  process; never shipped into sandbox containers.
- Per-org key pools with quota; no shared key between projects by default.

---

## 6. Prompt Injection & Tool Injection Defenses

| Attack | Defenses |
|---|---|
| Malicious text in fetched web pages trying to steer the agent | Research agents treat fetched content as **data**: quoted, provenance-tagged, outside instruction scope; guard prevents "instruction" role for retrieved content; system prompt reasserts boundaries each loop |
| Repo README injected commands | Developer agents use dependency/registry allow-list; never execute instructions found in fetched files; commit only explicitly planned changes |
| Tool result containing instructions | Tool outputs are structured data; prompts use `<data>` framing; models instructed to distinguish |
| Formula/CSV injection in generated artifacts | Output escaping for spreadsheet/HTML exports as part of generation rules |
| Indirect prompt injection via deployed app logs / incidents | Monitoring agent treats incident content as untrusted data; verification tasks don't auto-run without scope |

---

## 7. Malicious/Large Repos and Dependency Attacks

- Size limits on cloned repos; shallow clones; `.gitignore` enforcement no large blobs.
- Dependency installs go through the **registry allow-list** + checksum-pinned lockfiles and
  `dependency_audit` CVE scan prior to merge.
- No execute-from-remote scripts (e.g., `pip install https://...` blocked; `curl|sh` blocked).

---

## 8. Data Exfiltration Prevention

- Sandbox has **no default network egress**. Authorized egress to allow-listed hosts (web
  search API, registries) and via the egress proxy with destination + payload inspection.
- All outbound-from-sandbox traffic is tagged with the agent's project & run; anomalous
  volume triggers `data_flow_alert`.
- Artifact downloads are restricted to permitted channels.

---

## 9. SSRF & Server-Side Risks

- web_fetch: URL validation, port allow-list (80/443), DNS rebinding protection, no
  cloud-metadata IP ranges (169.254.x.x, 100.100.100.200, etc. denied), redirect policy
  restrictive.
- Deployment tooling strictly targets configured environments; no user-supplied
  deployment targets bypass config.

---

## 10. Credential / Supply Chain

- No plaintext secrets in code or CI. All generated infra bootstrap uses secret-manager
  references.
- Images pinned by digest; base images scanned; dependency audit on every PR.
- CI pipelines run with least-privilege tokens; no long-lived write tokens on agents.

---

## 11. Audit & Incident Response

- Immutable `audit_log` (cryptographic hash-chain optional in v1). Every sensitive action
  logged: who/what/when, request id, result.
- Policy-violation events auto-create incidents; T2+ incidents page humans.

---

## 12. Threat Model

See `39_SECURITY_THREAT_MODEL.md` for the enumerated STRIDE analysis and controls mapping.