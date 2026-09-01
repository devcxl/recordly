# Naming Conventions & Anti-Patterns

Consistent naming maintains order and prevents file collision across human and AI agent workflows.

---

## 1. Change Identifiers

- **Format**: Lowercase kebab-case, descriptive and concise.
- **Good**: `add-user-oauth`, `fix-jwt-expiration`, `migrate-pg-schema`, `optimize-cache-hit-ratio`
- **Bad**: `change1`, `fix_bug`, `temp_test`, `my-feature-final`

---

## 2. Decision History Documents (ADR & RFC)

- **ADR Format**: `ADR-<NUMBER>-<kebab-title>.md`
  - Example: `docs/03-architecture/adr/ADR-0001-use-postgresql.md`
  - Example: `docs/03-architecture/adr/ADR-0002-adopt-grpc.md`
- **RFC Format**: `RFC-<NUMBER>-<kebab-title>.md`
  - Example: `docs/03-architecture/rfc/RFC-0001-multi-tenant-isolation.md`
- **Numbering**: 4-digit sequential zero-padded integers (`0001`, `0002`, ...).

---

## 3. Current-State Documentation

- Use kebab-case for directories and filenames.
- Do not append version numbers or timestamps to current-state files (e.g. avoid `user-api-v2.md` unless the API version itself is explicitly v2).
- Rely on Git history for revision tracking rather than file cloning.

---

## 4. Strict Anti-Patterns

- **Never create**:
  - `*_final.md`
  - `*_v2_final.md`
  - `*_latest.md`
  - `*_copy.md`
  - `*_draft_2026.md`
- **Never rename** historical ADRs/RFCs after merging. Supersede them with a newer numbered ADR/RFC instead.
