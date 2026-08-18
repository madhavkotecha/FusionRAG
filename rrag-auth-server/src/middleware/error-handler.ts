/**
 * Global error handling.
 */

import type { Context } from "hono";
import type { AppEnv } from "../types.js";

export class AppError extends Error {
  constructor(
    public statusCode: number,
    message: string,
    public code?: string,
  ) {
    super(message);
    this.name = "AppError";
  }
}

export function errorHandler(err: Error, c: Context<AppEnv>) {
  if (err instanceof AppError) {
    return c.json(
      { error: err.message, code: err.code ?? undefined },
      err.statusCode as 400,
    );
  }

  // Unexpected error
  console.error("Unhandled error:", err);
  return c.json({ error: "Internal server error" }, 500);
}
