# ADR-0003: Multi-Tenant Workspace Data Model

## Status

Accepted

## Context

The system needs to support multiple organizations, each with multiple workspaces, with fine-grained access control. Data isolation between tenants is critical for security and compliance.

## Decision

Implement a three-level hierarchy: **Organization → Workspace → Resources**

- **Organization**: Top-level tenant. Users belong to exactly one org. Owns all workspaces.
- **Workspace**: Logical grouping within an org. Pipelines, documents, and API keys are workspace-scoped.
- **Roles**: Two levels — org-level (`org_admin`, `member`) and workspace-level (`admin`, `developer`, `viewer`).

All data queries include `workspace_id` filtering. The `AuthContext` carries workspace roles, and `require_workspace_access()` enforces access on every endpoint.

Cross-workspace access is supported via `workspace_access_grants` for controlled resource sharing.

## Consequences

**Positive:**
- Clean data isolation between organizations
- Granular access control within organizations
- Supports enterprise use cases (teams, departments as workspaces)
- API keys are workspace-scoped, limiting blast radius

**Negative:**
- Every query must include workspace context
- Cross-workspace operations require explicit grants
- User management is per-org (no global admin dashboard yet)

## Alternatives Considered

1. **Flat user model**: Simpler but no multi-tenancy
2. **Database-per-tenant**: Stronger isolation but higher operational overhead
3. **Row-level security (RLS)**: PostgreSQL RLS — considered too complex for initial implementation
