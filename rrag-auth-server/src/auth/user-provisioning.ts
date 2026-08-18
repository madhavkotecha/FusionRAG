/**
 * Auto-provision KC users on first login: creates org + user + workspace.
 * Shared between the auth middleware and /auth/me route handler.
 */

import { eq } from "drizzle-orm";
import * as schema from "../db/schema.js";

interface KcClaims {
  sub: string;
  email: string;
  name?: string;
  preferred_username?: string;
  realm_access?: { roles: string[] };
}

/**
 * Find an existing user by email, or auto-provision a new one from KC claims.
 * Returns the DB user row.
 */
export async function resolveOrProvision(db: any, kcClaims: KcClaims) {
  let [user] = await db
    .select()
    .from(schema.users)
    .where(eq(schema.users.email, kcClaims.email));

  if (!user) {
    const name =
      kcClaims.name ||
      kcClaims.preferred_username ||
      kcClaims.email.split("@")[0];

    const kcRoles = kcClaims.realm_access?.roles ?? [];
    const orgRole = kcRoles.includes("rrag_admin") ? "org_admin" : "member";
    const isPlatformAdmin = kcRoles.includes("rrag_platform_admin");

    const orgSlug = `kc-${kcClaims.email.split("@")[0].replace(/[^a-z0-9-]/g, "-")}`;

    const result = await db.transaction(async (tx: any) => {
      let slug = orgSlug;
      const [existingOrg] = await tx
        .select()
        .from(schema.organizations)
        .where(eq(schema.organizations.slug, slug));
      if (existingOrg) {
        slug = `${orgSlug}-${Date.now().toString(36)}`;
      }

      const [org] = await tx
        .insert(schema.organizations)
        .values({ name: `${name}'s Org`, slug })
        .returning();

      const [newUser] = await tx
        .insert(schema.users)
        .values({
          orgId: org.id,
          email: kcClaims.email,
          name,
          passwordHash: null,
          orgRole,
          isPlatformAdmin,
          status: "active",
        })
        .returning();

      const [workspace] = await tx
        .insert(schema.workspaces)
        .values({
          orgId: org.id,
          name: `${name}'s Workspace`,
          slug: `${slug}-personal`,
          scope: "personal",
          ownerUserId: newUser.id,
        })
        .returning();

      await tx.insert(schema.workspaceMembers).values({
        workspaceId: workspace.id,
        userId: newUser.id,
        role: "admin",
      });

      return newUser;
    });

    user = result;
  } else {
    // Sync roles from KC on every login
    const kcRoles = kcClaims.realm_access?.roles ?? [];
    const orgRole = kcRoles.includes("rrag_admin") ? "org_admin" : "member";
    const isPlatformAdmin = kcRoles.includes("rrag_platform_admin");
    const [updated] = await db
      .update(schema.users)
      .set({ lastLoginAt: new Date(), isPlatformAdmin, orgRole })
      .where(eq(schema.users.id, user.id))
      .returning();
    user = updated ?? user;
  }

  return user;
}
