# ADR-0030: Admin Component Management with Append-Only Versioning

- **Status:** Accepted
- **Date:** 2026-03-22
- **Deciders:** Architecture Team
- **Relates to:** ADR-0016 (Component Registry Pattern), ADR-0026 (Hierarchical Composite Components)

## Context

The composite-component framework (ADR-0026) lets users upload Python components at runtime via MinIO. Two problems emerged once the system had real users:

1. **No history.** Editing a component overwrote its source. There was no way to roll back a broken change or audit who changed what.
2. **No platform-level admin.** Every workspace could upload its own components, but the platform-admin role had no view across workspaces and could not curate a canonical set of "seed" components.

## Decision

Introduce two coupled features:

### 1. Append-only component versions (`component_versions` table)

Each upload of a component (built-in or user-defined) appends a row capturing:

| Field | Purpose |
|-------|---------|
| `component_type` | Logical name |
| `workspace_id` | Tenancy |
| `version` (int) | Monotonic per (component_type, workspace_id) |
| `code` (text) | Full source at this version |
| `file_hash` (sha256, 64 chars) | Idempotency / dedup |
| `changed_by` (user id) | Audit |
| `change_reason` (free text) | Audit |
| `created_at` | Timestamp |

Unique constraint `(component_type, workspace_id, version)` enforces append-only semantics. No row is ever updated or deleted.

Service: `rrag-pipeline-service/src/pipeline_service/services/component_versions.py`. Model + migration: `models/component_version.py`, `alembic/versions/006_add_component_versions.py`.

### 2. Platform-admin component management

A `platform_admin` realm role (seeded in Keycloak as `rrag_platform_admin`) unlocks a dedicated admin surface:

- **Backend:** `rrag-pipeline-service/src/pipeline_service/api/admin_components.py` — list across workspaces, edit, view version history, rollback by re-uploading an old version, mark as "seed".
- **Frontend:** `rrag-frontend/src/pages/AdminComponentsPage.tsx` — table view with code editor (Monaco) + version-history sidebar.
- **Seed bootstrap:** `services/seed_bootstrap.py` generates the canonical `.py` files for every seed component on startup, ensuring fresh installs have a working baseline before any user uploads.
- **Guard:** `AdminGuard` (frontend) and `auth.require_platform_admin()` (backend) gate access. Auth-server provisioning (`rrag-auth-server/src/auth/user-provisioning.ts`) syncs the role from Keycloak.

### Cache invalidation

Component upload invalidates the Redis component-cache key for the workspace immediately (commit `4b90290`) so newly uploaded versions are picked up on the next pipeline build.

## Consequences

**Positive:**
- Full audit trail: every component edit is durably attributed and reproducible
- Rollback is trivial: load any prior version's `code` field and re-upload
- Platform admins can curate seed components without per-workspace duplication
- Append-only design means version history is tamper-evident (no edits to past rows)

**Negative:**
- Disk growth: every upload adds a row with full source text. Mitigated by `file_hash` dedup at the application layer (skip insert if hash matches latest version).
- No diff view in UI today — admins see full versions side-by-side, not a unified diff (planned)
- Rollback creates a new version rather than reverting in place, which is the right design but can confuse users expecting "git revert" semantics

## Alternatives Considered

1. **Store components in Git** — full version control, but adds a Git server dependency and complicates per-workspace isolation.
2. **Update-in-place with `prev_code` column** — only one level of history; doesn't scale.
3. **Soft-delete + revisions table** — equivalent to the chosen design but with mutable "current" rows; chose append-only for simpler auditability.

## References

- Commits: `925581e` (model + migration), `29b8e1a` (versions service), `6ffda6e` (admin API), `1e3498f` (admin UI), `f733121` (AdminGuard + sidebar), `03e579e` (seed bootstrap), `7b65272` (version record on upload), `4b90290` (cache invalidation)
- Files: `rrag-pipeline-service/src/pipeline_service/api/admin_components.py`, `services/component_versions.py`, `models/component_version.py`, `alembic/versions/006_add_component_versions.py`, `rrag-frontend/src/pages/AdminComponentsPage.tsx`, `rrag-frontend/src/pages/ComponentCreatorPage.tsx`
