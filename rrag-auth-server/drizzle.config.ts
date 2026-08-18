import path from "path";
import dotenv from "dotenv";
import { defineConfig } from "drizzle-kit";

// Load root .env (one level up from rrag-auth-server/)
dotenv.config({ path: path.resolve(__dirname, "../.env") });

if (!process.env.DATABASE_URL) {
  throw new Error("DATABASE_URL is not set. Check your root .env file.");
}

export default defineConfig({
  schema: "./src/db/schema.ts",
  out: "./drizzle/migrations",
  dialect: "postgresql",
  dbCredentials: {
    url: process.env.DATABASE_URL,
  },
});
