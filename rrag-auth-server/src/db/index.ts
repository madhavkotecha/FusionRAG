/**
 * Drizzle ORM client singleton.
 */

import { drizzle } from "drizzle-orm/node-postgres";
import pg from "pg";
import * as schema from "./schema.js";

let _db: ReturnType<typeof drizzle<typeof schema>> | null = null;
let _pool: pg.Pool | null = null;

export type DrizzleDB = ReturnType<typeof drizzle<typeof schema>>;

export function getDb(databaseUrl?: string): DrizzleDB {
  if (_db) return _db;

  const url = databaseUrl ?? process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL is required");

  _pool = new pg.Pool({ connectionString: url });
  _db = drizzle(_pool, { schema });
  return _db;
}

/** Override the DB instance (used in tests). */
export function setDb(db: DrizzleDB): void {
  _db = db;
}

/** Close the connection pool. */
export async function closeDb(): Promise<void> {
  if (_pool) {
    await _pool.end();
    _pool = null;
    _db = null;
  }
}

export { schema };
