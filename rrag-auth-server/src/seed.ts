/**
 * Seed script: creates a superadmin user with org, workspace, and membership.
 *
 * All config is read from environment variables (or root .env via dotenv).
 *
 * Usage:
 *   npm run db:seed              # reads DATABASE_URL + SEED_* from .env
 *   DATABASE_URL=... npm run db:seed   # override via env
 */

import dotenv from "dotenv";
import path from "path";
import { fileURLToPath } from "url";

// Load root .env (two levels up from rrag-auth-server/src/)
const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.resolve(__dirname, "../../.env") });

import pg from "pg";
import { drizzle } from "drizzle-orm/node-postgres";
import { eq } from "drizzle-orm";
import bcrypt from "bcryptjs";
import * as schema from "./db/schema.js";

const DATABASE_URL = process.env.DATABASE_URL;
if (!DATABASE_URL) {
  console.error("ERROR: DATABASE_URL is not set. Check your .env file.");
  process.exit(1);
}

const SEED_EMAIL = process.env.SEED_EMAIL;
const SEED_PASSWORD = process.env.SEED_PASSWORD;
const SEED_NAME = process.env.SEED_NAME ?? "Admin";
const SEED_ORG_NAME = process.env.SEED_ORG_NAME ?? "Default Org";
const SEED_ORG_SLUG = process.env.SEED_ORG_SLUG ?? "default-org";

if (!SEED_EMAIL || !SEED_PASSWORD) {
  console.error("ERROR: SEED_EMAIL and SEED_PASSWORD must be set. Check your .env file.");
  process.exit(1);
}

async function seed() {
  const pool = new pg.Pool({ connectionString: DATABASE_URL });
  const db = drizzle(pool, { schema });

  try {
    // Check if user already exists
    const [existing] = await db
      .select()
      .from(schema.users)
      .where(eq(schema.users.email, SEED_EMAIL));

    if (existing) {
      console.log(`User ${SEED_EMAIL} already exists (id: ${existing.id}). Skipping seed.`);
      return;
    }

    // Check if org slug is taken
    const [existingOrg] = await db
      .select()
      .from(schema.organizations)
      .where(eq(schema.organizations.slug, SEED_ORG_SLUG));

    if (existingOrg) {
      console.log(`Org slug "${SEED_ORG_SLUG}" already exists. Skipping seed.`);
      return;
    }

    const passwordHash = await bcrypt.hash(SEED_PASSWORD, 12);

    const result = await db.transaction(async (tx) => {
      const [org] = await tx
        .insert(schema.organizations)
        .values({ name: SEED_ORG_NAME, slug: SEED_ORG_SLUG })
        .returning();

      const [user] = await tx
        .insert(schema.users)
        .values({
          orgId: org.id,
          email: SEED_EMAIL,
          name: SEED_NAME,
          passwordHash,
          orgRole: "org_admin",
          status: "active",
        })
        .returning();

      const [workspace] = await tx
        .insert(schema.workspaces)
        .values({
          orgId: org.id,
          name: "Default Workspace",
          slug: `${SEED_ORG_SLUG}-default`,
        })
        .returning();

      await tx.insert(schema.workspaceMembers).values({
        workspaceId: workspace.id,
        userId: user.id,
        role: "admin",
      });

      return { org, user, workspace };
    });

    console.log("Seed completed successfully:");
    console.log(`  Org:       ${result.org.name} (${result.org.id})`);
    console.log(`  User:      ${result.user.email} (${result.user.id})`);
    console.log(`  Role:      ${result.user.orgRole}`);
    console.log(`  Workspace: ${result.workspace.name} (${result.workspace.id})`);
  } catch (err) {
    console.error("Seed failed:", err);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

seed();
