# Enforcement, Branch Protection & Tamper Resistance

CLI checks are only authoritative if the underlying repository protections prevent actors (both human and AI agents) from bypassing or disabling them.

---

## 1. Threat Model & Autonomous Agent Boundary

When AI coding agents operate on repositories with direct commit or PR creation privileges, the following risks must be mitigated:

1. **Bypassing Workflow Gates**: Agent directly modifying `.cabbage/changes/*/state.json` without running `cabbage verify`.
2. **Weakening CI Policies**: Agent modifying `.github/workflows/cabbage.yml` or deleting `.cabbage/workflows/` to allow failing PRs to pass.
3. **Ghost Code Delivery**: Modifying source code without an associated verified Cabbage change record.

---

## 2. Mandatory Repository Protections

To establish a zero-trust, tamper-resistant document lifecycle:

### A. Branch Protection Rules (GitHub / GitLab)
- **Require Pull Request**: Disallow direct pushes to default/protected branches (`main`, `master`, `release/*`).
- **Require Status Checks**: Make the `cabbage` CI job a mandatory status check before merge.
- **Require Approvals**: Require at least 1 human approval for PRs modifying core configurations.

### B. CODEOWNERS Restrictions
Enforce code ownership on governance paths:

```text
/.cabbage/config.yaml @tech-lead @platform-team
/.cabbage/workflows/** @tech-lead @platform-team
/.cabbage/tooling/** @tech-lead @platform-team
/.github/workflows/cabbage.yml @tech-lead @devops
```

### C. State Protection
Treat `.cabbage/changes/*/state.json` as CLI-owned binary state. Never edit this file manually; always let `cabbage verify` compute and record valid SHA-256 signatures.

---

## 3. Strict Mode in CI

Ensure CI executes `cabbage ci` in strict mode on every pull request:

```yaml
- name: Cabbage CI Gate Check
  run: |
    cabbage ci --base origin/${{ github.base_ref || 'main' }}
    cabbage docs build
```
