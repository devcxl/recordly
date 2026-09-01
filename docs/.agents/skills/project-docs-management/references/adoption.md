# Adoption: bringing an existing project into cabbage

`cabbage init` assumes a greenfield project. For a project that already has documentation, use the adoption flow below. The CLI only inventories; humans and agents decide and move.

## When to use

Run `cabbage adopt` after `cabbage init` when the repository already contains long-lived documents (design docs, ADRs, runbooks, API references) that live outside the standard `docs/` tree.

## Phase 1: Initialize without disturbing content

```bash
cabbage init
```

`init` only adds `.cabbage/`, the `docs/` VitePress skeleton, and CI wiring. It never removes or rewrites existing files. If a `docs/` directory already exists with different content, review each scaffold file before accepting it.

## Phase 2: Inventory

```bash
cabbage adopt [--json]
```

This scans every Markdown file outside the docs tree and writes `.cabbage/adoption-report.md`. No files are moved. Each document gets one action:

| Action | Meaning |
|---|---|
| `keep` | Already inside the standard numbered tree; nothing to do |
| `migrate` | Current-state document; move into the standard tree |
| `import` | Historical record (ADR/RFC/incident); archive as-is |
| `review` | Unclassified; decide by hand |

Classification is a suggestion from directory/file names (e.g. `adr/` → ADR, `runbooks/` → operations). Always confirm before moving.

## Phase 3: Resolve review rows

For every `review` row, decide with the document owner:

- current-state content → migrate it and pick a target from `references/directory-structure.md`;
- historical decision or incident record → import as immutable history;
- stale duplicate or scratch note → delete it in the same PR (Git keeps history).

Edit the report or annotate the rows so the final decision is recorded.

## Phase 4: Migrate current-state documents

Move files with `git mv` so history follows the file:

1. Create the target directory only if it has real content (`docs/01-product/`, `docs/03-architecture/`, ...).
2. Move the file, then fix intra-project links: relative links must resolve from the new location.
3. Do not rename content into `final-v2.md` style; keep stable paths. Git stores history.
4. One logical batch per commit (e.g. all runbooks together) so review stays readable.

After each batch:

```bash
cabbage docs build
```

## Phase 5: Import historical records

ADR, RFC and incident documents are decision history, not current state:

- Copy or move them under `docs/03-architecture/adr/`, `docs/03-architecture/rfc/`, `docs/15-incidents/`.
- Do not rewrite, "modernize", or merge their content; superseded decisions stay visible.
- If two records conflict, the newer one supersedes the older explicitly; do not edit the older one.

## Phase 6: Baseline and first change

1. Record the completed migration in a change record so the work itself is auditable:

   ```bash
   cabbage new feature adopt-existing-docs
   ```

2. Fill `prd.md` and `tasks.md` with what was moved and what remains; complete the stages you actually ran.
3. Verify the site builds and links resolve: `cabbage validate adopt-existing-docs` and `cabbage docs build`.
4. Merge. From this point on, the normal skill rules apply to every new change.

## Phase 7: Enable enforcement

Only after the baseline merged:

1. Set the GitHub Actions `cabbage` job as a required status check (see `references/enforcement.md`).
2. Require human review for `.cabbage/config.yaml`, `.cabbage/workflows/**`, `.cabbage/tooling/**` and CI files.
3. Keep `cabbage adopt` available: re-running it after the baseline should report `keep` for every document; anything else indicates drift.

## Rules

1. `cabbage adopt` never moves files; moves are deliberate, reviewed Git operations.
2. Historical records are imported, never rewritten.
3. Every move fixes links in the same commit.
4. Adoption is itself a change record, subject to the same gates as feature work.
