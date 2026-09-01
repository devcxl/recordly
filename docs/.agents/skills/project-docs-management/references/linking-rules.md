# Markdown Linking & Anchor Rules

Broken links destroy documentation credibility. Cabbage and VitePress strictly enforce link integrity across all Markdown documents.

---

## 1. Core Linking Principles

1. **Relative Paths Over Absolute Paths**:
   - Always use relative file paths for intra-project document links:
     - Good: `[ADR-0001](../03-architecture/adr/ADR-0001-auth.md)`
     - Bad: `[ADR-0001](/docs/03-architecture/adr/ADR-0001-auth.md)`
2. **Single Source of Truth**:
   - Link to the canonical document rather than duplicating information across multiple files.
3. **Explicit File Extensions**:
   - Always include the `.md` extension in Markdown links to ensure resolution both in raw Git repositories and in VitePress builds.
4. **Stable Heading Anchors**:
   - When linking to a specific section, use standard GitHub-compatible lowercase hyphenated slugs:
     - Example: `[Rollback Plan](release-plan.md#rollback-procedure)`

---

## 2. Cross-Document Reference Patterns

- **From Active Change Workspace to Current-State Docs**:
  - `[Current Architecture](../../docs/03-architecture/system-design/overview.md)`
- **From Current-State Docs to ADRs**:
  - `[ADR-0002 Storage Selection](adr/ADR-0002-postgresql.md)`
- **From Code / Comments to Documentation**:
  - Point to stable canonical documents under `docs/` rather than volatile change workspaces (`.cabbage/changes/`).

---

## 3. Automated Validation

`cabbage validate` automatically scans all Markdown files and verifies:
- Target files exist on disk.
- Heading anchor `#slug` targets exist within the destination file.
- Relative paths resolve cleanly without traversing outside the project root.
