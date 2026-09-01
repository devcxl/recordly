# Cabbage CLI Reference

Comprehensive command-line interface specification for Cabbage document lifecycle management.

## Syntax & Exit Codes

```bash
cabbage <command> [arguments] [options]
```

### Exit Codes

- `0` (`SUCCESS`): Command completed successfully, validation passed, or gate allowed.
- `1` (`VALIDATION_ERROR` / `GATE_BLOCKED`): Artifact validation failed, gate check blocked, or CI check failed.
- `2` (`USAGE_ERROR` / `SYSTEM_ERROR`): Invalid arguments, missing configuration, corrupted workflow, or unexpected error.

---

## Command Matrix

### 1. Environment & Initialization

#### `cabbage doctor [--json]`
Diagnose runtime environment and project dependencies.
- **Checks**: Python (>= 3.10), PyYAML, Git CLI, pnpm CLI, Cabbage project integrity.
- **Flags**: `--json` output structured diagnostic report.

```bash
cabbage doctor
```

#### `cabbage init [--force] [--no-vendor-cli]`
Initialize a greenfield project with `.cabbage/` configuration, workflows, and `docs/` VitePress documentation site.
- **Flags**:
  - `--force`: Overwrite existing `.cabbage/` configuration and templates.
  - `--no-vendor-cli`: Skip bundling the CLI script into `.cabbage/tooling/`.

```bash
cabbage init
```

#### `cabbage adopt [--apply] [--json]`
Inventory and optionally migrate existing project documentation outside the `docs/` directory.
- **Flags**:
  - `--apply`: Automatically apply suggested moves (`migrate` and `import`) using Git.
  - `--json`: Output inventory JSON.
- **Reference**: See `references/adoption.md` for the complete 7-phase adoption guide.

```bash
cabbage adopt
cabbage adopt --apply
```

---

### 2. Change Lifecycle Management

#### `cabbage new <type> <change-id>`
Create a new active change workspace under `.cabbage/changes/<change-id>/`.
- **Arguments**:
  - `<type>`: `feature` | `architecture` | `bugfix` | `hotfix` | `refactor` | `migration` | `integration` | `incident`
  - `<change-id>`: Unique identifier in kebab-case (e.g., `user-oauth-login`).
- **Behavior**: Scaffolds workflow artifacts, initializes `state.json`, and outputs initial stage status.

```bash
cabbage new feature user-oauth-login
```

#### `cabbage status [change-id] [--json]`
Display the progress and verification status of a specific change or all active changes.
- **Stage Statuses**:
  - `pending`: Artifact template created but not yet verified.
  - `done`: Verified with valid SHA-256 signature and all dependencies satisfied.
  - `stale`: Upstream dependency, workflow definition, or artifact was modified after verification.
  - `skipped`: Deactivated by current impact matrix settings.

```bash
cabbage status user-oauth-login
cabbage status --json
```

#### `cabbage next <change-id> [--json]`
Inspect ready (unblocked) stages and blocked stages based on workflow dependency graph.

```bash
cabbage next user-oauth-login
```

#### `cabbage impact <change-id> [--set field=true|false] [--json]`
Inspect or mutate the impact analysis matrix of a change.
- **Available Fields**: `product`, `architecture`, `api`, `database`, `security`, `testing`, `deployment`, `operations`, `data`, `performance`.
- **Behavior**: Mutating impact updates `change.yaml`, generates conditional artifact templates, and resets downstream stages to `stale`.

```bash
cabbage impact user-oauth-login --set api=true --set database=true
```

#### `cabbage discard <change-id>`
Delete an active change workspace and clean up its pending artifacts.

```bash
cabbage discard user-oauth-login
```

---

### 3. Verification & Quality Gates

#### `cabbage verify <change-id> <stage>`
Verify a single stage artifact, check content completeness, ensure no placeholders or unchecked tasks, and record the cryptographic signature in `state.json`.
- **Checks**:
  - All upstream dependencies are in `done` state.
  - Artifact file exists and frontmatter matches change ID and stage.
  - Required section headings are present.
  - No legacy placeholders or `TODO` / `TBD` / `FIXME` / `CABBAGE` markers remain.
  - No unchecked tasks (`- [ ]`) remain in task-oriented stages.
  - Markdown local links and anchor references resolve.
  - Mermaid diagram syntax fences are closed.

```bash
cabbage verify user-oauth-login prd
cabbage verify user-oauth-login tasks
```

#### `cabbage validate [<change-id> | --all] [--json]`
Validate Markdown integrity, frontmatter, heading structures, and link resolution across one or all active changes.

```bash
cabbage validate user-oauth-login
cabbage validate --all
```

#### `cabbage gate <change-id> <target> [--json]`
Evaluate readiness for specific milestones in the software development lifecycle.
- **Targets**:
  - `implementation`: Enforces that PRD, tech-spec, architecture, and task artifacts are verified before code changes begin.
  - `merge`: Enforces that all active workflow stages (testing, release, documentation) are verified before merging PR.
  - `archive`: Enforces that the entire change lifecycle is completed before archiving.

```bash
cabbage gate user-oauth-login implementation
cabbage gate user-oauth-login merge
cabbage gate user-oauth-login archive
```

---

### 4. Sync, Archive & CI

#### `cabbage sync <change-id> [--json]`
Extract verified specifications (e.g. API designs, ADRs, database schemas) and synchronize them into the persistent `docs/` tree.

```bash
cabbage sync user-oauth-login
```

#### `cabbage archive <change-id>`
Validate the `archive` gate, sync final specifications to `docs/`, mark status as `archived`, and move the workspace to `.cabbage/archive/<YEAR>/<change-id>/`.

```bash
cabbage archive user-oauth-login
```

#### `cabbage ci --base <git-ref>`
Continuous Integration runner. Validates Git diff, verifies that code modifications are bound to valid Cabbage changes, checks all active changes, and ensures docs build cleanly.

```bash
cabbage ci --base origin/main
```

---

### 5. Documentation Site Operations

#### `cabbage docs <install|dev|build>`
Manage the embedded VitePress documentation site under `docs/`.
- `install`: Run `pnpm install` in `docs/`.
- `dev`: Launch local live-reload VitePress development server.
- `build`: Execute static production build (`docs/.vitepress/dist/`).

```bash
cabbage docs install
cabbage docs dev
cabbage docs build
```
