# Workflow & Change Type Decision Tree

This guide defines how to classify changes, dispatch appropriate workflow paths, and activate conditional artifacts in Cabbage.

---

## 1. Scenario Dispatch Matrix (Phase 0)

Before creating a change workspace, evaluate the input against the 10 scenario archetypes:

| Scenario Archetype | Key Characteristics | Cabbage Change Type | Execution Path | Key Actions & Exit Criteria |
|---|---|---|---|---|
| **New Capability / Feature** | User-visible or new business capabilities | `feature` | Full Lifecycle | PRD -> Tech Spec -> Tasks -> Implementation -> Dual-Axis Review -> Merge |
| **Bug / Regression** | Defect in merged code or non-outage regression | `bugfix` | Lightweight Corrective | Reproduce -> Failing Test (RED) -> Minimal Fix (GREEN) -> Regression Verify |
| **Production Incident / Hotfix** | P0/P1 live outage or urgent production patch | `hotfix` or `incident` | Fast-Track Patch | Patch from release tag -> Minimal Fix -> Release PR -> Rollback plan |
| **Business Adjustment** | Minor adjustments to existing behavior/fields | `feature` or `bugfix` | Change Management | Impact analysis -> Backward compatibility check -> Update spec -> Implement |
| **Refactoring** | Internal restructuring without behavior changes | `refactor` | Behavior-Preserving | Test safety net -> Stepwise refactor -> Differential/snapshot parity check |
| **Tech Debt Cleanup** | Dead code, obsolete configs, unused assets | `refactor` | Behavior-Preserving Removal | Inventory unused assets -> Verify consumer references -> Delete -> Full regression |
| **Infrastructure Change** | CI/CD, build tools, package dependencies | `integration` or `refactor` | CI-as-Acceptance | Small incremental steps -> Push to CI -> Verify build pipeline & regression |
| **Documentation Update** | Standalone docs updates, runbooks, guides | `feature` or direct docs | Docs-as-Code | Update canonical docs -> Terminology check -> Docs build verify (`cabbage docs build`) |
| **Rollback & Recovery** | Failed deployment, critical release issue | `hotfix` | Controlled Rollback | Revert PR -> Create root-cause corrective change -> Clean worktrees |
| **Technical Research** | Tech evaluation, spike, architectural study | `architecture` | Evidence-Driven | Frame hypothesis -> Conduct research/POC -> Document findings & trade-offs |

---

## 2. Classification Decision Tree

```text
Change Intake
│
├── Adds new business capability or user-visible feature?
│   └── -> Type: `feature` (Full lifecycle)
│
├── Alters system boundaries, runtime topology, major tech stack, or distributed protocols?
│   └── -> Type: `architecture` (Tech Spec + ADR + Topology)
│
├── Corrects a non-production-outage functional defect or regression?
│   └── -> Type: `bugfix` (Lightweight corrective path)
│
├── Urgent production patch requiring rapid hot-patching?
│   └── -> Type: `hotfix` (Fast-track release path)
│
├── Internal structural refactoring without external behavioral changes?
│   └── -> Type: `refactor` (Behavior-preserving path)
│
├── Database schema evolution, data backfill, or platform/runtime migration?
│   └── -> Type: `migration` (Schema + Rollback + Data safety)
│
├── Connecting with third-party APIs, webhooks, or external SaaS platforms?
│   └── -> Type: `integration` (API Design + Security Review)
│
└── Production incident response, post-mortem, and corrective action tracking?
    └── -> Type: `incident` (Timeline + 5-Why Postmortem)
```

---

## 3. Impact Analysis Matrix & Conditional Activation

Impact analysis determines which conditional stages are activated in active change workflows. Run:

```bash
cabbage impact <change-id> --set <field>=true|false
```

| Impact Field | When to Enable (`true`) | Activated Artifact / Stage |
|---|---|---|
| `product` | Changes product behavior, user workflows, or UI/UX | `prd` |
| `architecture` | Introduces new components, alters boundaries, or introduces ADRs | `tech-spec`, `adr` |
| `api` | Modifies REST/GraphQL/gRPC interfaces, DTOs, or webhooks | `api-design` |
| `database` | Adds/modifies tables, fields, indexes, or requires data backfill | `database-design` |
| `security` | Touches auth, permissions, secrets, PII, or attack surface | `security-review` |
| `testing` | Requires special test scenarios, load testing, or E2E suites | `test-plan` |
| `deployment` | Involves infra changes, env vars, migrations, or release steps | `release-plan` |
| `operations` | Changes logging, alerting, metrics, or runbooks | `runbooks` |
| `data` | Alters data pipelines, ETL, caching, or event streaming | `data-flow` |
| `performance` | Performance-critical changes, latency/throughput requirements | `benchmark` |

---

## 4. Operational Principles

1. **Lightweight Paths for Non-Feature Scenarios**: For bugfixes, tech debt cleanups, or refactoring, avoid heavy PRD ceremonies unless the root cause stems from architectural flaws.
2. **Never Create Redundant Standalone Docs**: Activate conditional stages within the managed change workflow and sync them to `docs/`.
3. **Cascading Invalidation Awareness**: Changing impact flags triggers downstream stages to become `stale`. Always inspect ready stages with `cabbage next <change-id>`.
