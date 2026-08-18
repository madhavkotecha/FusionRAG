/**
 * Programmatic Drizzle migration runner.
 * Uses drizzle-orm/migrator (prod dependency) instead of drizzle-kit (dev-only).
 */

import { drizzle } from "drizzle-orm/node-postgres";
import { migrate } from "drizzle-orm/node-postgres/migrator";
import pg from "pg";

async function main() {
  const url = process.env.DATABASE_URL;
  if (!url) {
    console.error("DATABASE_URL is required");
    process.exit(1);
  }

  console.log("Running database migrations...");
  const pool = new pg.Pool({ connectionString: url });

  try {
    const db = drizzle(pool);
    await migrate(db, { migrationsFolder: "./drizzle/migrations" });
    console.log("Migrations completed successfully.");
  } catch (err: unknown) {
    // Handle "relation already exists" — tables were created by a prior run
    // but the drizzle journal may not have recorded them (e.g. volume persisted
    // across rebuilds while the journal table was lost or never created).
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("already exists")) {
      console.warn("Tables already exist — skipping migration.", msg);
    } else {
      console.error("Migration failed:", err);
      process.exit(1);
    }
  } finally {
    await pool.end();
  }
}

main();
