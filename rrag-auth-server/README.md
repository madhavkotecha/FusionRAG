# rrag-auth-server

Enterprise authentication and authorization server for the RRAG platform. Built with **Hono**, **Drizzle ORM**, and **PostgreSQL**.

## Stack

| Layer | Tech |
|---|---|
| Framework | Hono v4 |
| ORM | Drizzle ORM + drizzle-kit |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Auth | JWT (HS256) + refresh token rotation |
| Validation | Zod |
| Testing | Vitest |

## Quick Start

```bash
# Install deps
npm install

# Start infra + dev server (hot reload)
make dev

# Or start everything in Docker
make up
```

## API Endpoints (24)

### Auth (`/auth`)
| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create org + admin user + default workspace |
| POST | `/auth/login` | Email/password login → JWT + refresh token |
| POST | `/auth/token/refresh` | Rotate refresh token |
| POST | `/auth/logout` | Revoke single session |
| POST | `/auth/logout/all` | Revoke all user sessions |
| GET | `/auth/me` | Current user profile + workspaces |
| GET | `/auth/sessions` | List active sessions |
| DELETE | `/auth/sessions/:id` | Revoke specific session |

### Users (`/users`) — requires org_admin
| Method | Path | Description |
|---|---|---|
| GET | `/users` | List org users |
| POST | `/users/invite` | Invite user by email |
| PUT | `/users/:id/role` | Update org role |
| PUT | `/users/:id/status` | Suspend / activate |

### Workspaces (`/workspaces/:wsId/members`)
| Method | Path | Description |
|---|---|---|
| GET | `/workspaces/:wsId/members` | List members |
| POST | `/workspaces/:wsId/members` | Add member |
| PUT | `/workspaces/:wsId/members/:userId` | Update role |
| DELETE | `/workspaces/:wsId/members/:userId` | Remove member |

### API Keys (`/workspaces/:wsId/api-keys`)
| Method | Path | Description |
|---|---|---|
| GET | `/workspaces/:wsId/api-keys` | List keys |
| POST | `/workspaces/:wsId/api-keys` | Create key |
| DELETE | `/workspaces/:wsId/api-keys/:keyId` | Revoke key |

### SSO (`/org/sso`) — stubs, returns 501
### Audit (`/audit-logs`) — query with filters + pagination

## RBAC

5-tier role hierarchy: `platform_admin > org_admin > admin > developer > viewer`

Permission format: `resource:action` (e.g. `pipeline:create`, `workspace.members:manage`)

## Database Schema (10 tables)

`organizations` → `users`, `workspaces` → `workspace_members`, `api_keys`, `sessions`, `audit_logs`, `sso_configs`, `user_invitations`, `workspace_access_grants`

Migrations managed by Drizzle Kit. Schema defined in `src/db/schema.ts`.

## Commands

```bash
make help          # Show all commands
make dev           # Dev server with hot reload
make up            # Docker compose up (all services)
make down          # Stop services
make test          # Run full test suite (55 tests)
make migrate       # Run DB migrations
make db-generate   # Generate migration from schema changes
make build         # Compile TypeScript
make typecheck     # Type check without emit
```

## Project Structure

```
src/
├── index.ts              # Entry point
├── app.ts                # Hono app factory
├── config.ts             # Zod-validated env config
├── types.ts              # AuthContext, AppEnv
├── db/                   # Schema (10 tables), DB + Redis clients
├── middleware/            # auth, rate-limiter, error-handler, request-id, timing
├── token/                # JWT + refresh token lifecycle
├── rbac/                 # Permission matrix + middleware
├── auth/                 # Register, login, refresh, logout, sessions
├── users/                # List, invite, update role/status
├── workspaces/           # Member CRUD
├── api-keys/             # Create, list, revoke
├── sso/                  # Stubs (Phase 3)
└── audit/                # Audit log query + logger helper
```

## Environment Variables

Copy `.env.example` to `.env` and update values. All variables are validated at startup via Zod.
