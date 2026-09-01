# Documentation Ownership & Governance

Documentation without clear ownership degrades quickly. In Cabbage, documentation ownership directly reflects system and module ownership.

---

## 1. Ownership Principles

1. **Code & Documentation Parity**: The engineering team or engineer that owns a service/module is responsible for its architecture, API, database schema, and runbook documentation.
2. **Atomic Ownership**: PRs modifying system behavior must update the corresponding module documentation within the same PR.
3. **Explicit Frontmatter Attribution**: Critical long-lived documentation should declare ownership in frontmatter:

```yaml
---
title: Payment Service Architecture
owner: team-billing
maintained-by:
  - "@alice"
  - "@bob"
last-reviewed: 2026-03-01
---
```

---

## 2. CODEOWNERS Integration

Repositories should leverage `.github/CODEOWNERS` to ensure document changes are reviewed by respective domain leads:

```text
# Architecture & ADRs require Principal / Architect review
/docs/03-architecture/ @lead-architect

# Security reviews require SecOps approval
/docs/09-security/ @security-team

# Cabbage workflow and CI configuration require human tech lead approval
/.cabbage/config.yaml @tech-lead
/.cabbage/workflows/ @tech-lead
/.github/workflows/cabbage.yml @tech-lead
```
