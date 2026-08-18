/**
 * Global test setup.
 *
 * Sets environment variables required by config.ts before any imports.
 * Uses ioredis-mock for Redis.
 * For DB, tests use a real PostgreSQL via docker-compose or skip DB-dependent tests.
 */

// Set test env vars BEFORE config.ts is imported
process.env.ENVIRONMENT = "test";
process.env.DATABASE_URL = process.env.TEST_DATABASE_URL ?? "postgresql://rrag:rrag_dev_password@localhost:5432/rrag_test";
process.env.REDIS_URL = "redis://localhost:6379/1";
process.env.JWT_SECRET_KEY = "test-secret-key-at-least-32-characters-long";
process.env.JWT_ALGORITHM = "HS256";
process.env.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = "15";
process.env.JWT_REFRESH_TOKEN_EXPIRE_DAYS = "7";
process.env.JWT_ISSUER = "https://auth.rrag.io";
process.env.JWT_AUDIENCE = "https://api.rrag.io";
process.env.PORT = "0";
process.env.PASSWORD_MIN_LENGTH = "12";
process.env.PASSWORD_MAX_FAILED_ATTEMPTS = "5";
process.env.PASSWORD_LOCKOUT_MINUTES = "15";
process.env.RATE_LIMIT_UNAUTHENTICATED = "1000";
process.env.RATE_LIMIT_AUTHENTICATED = "1000";
process.env.RATE_LIMIT_API_KEY = "1000";
process.env.INVITATION_EXPIRE_HOURS = "72";

export {};
