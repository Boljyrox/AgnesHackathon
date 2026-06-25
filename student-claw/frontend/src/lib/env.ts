/**
 * Centralised environment + session constants for the BFF gateway.
 *
 * This module is edge-safe: it touches only `process.env` (statically
 * inlined by Next) and exports plain constants, so it can be imported from
 * `middleware.ts` (Edge runtime) as well as Node route handlers.
 */

export const COOKIE_NAMES = {
  access: "access_token",
  refresh: "refresh_token",
} as const;

// Token lifetimes (seconds) — blueprint §6.2.
export const ACCESS_TOKEN_MAX_AGE = 15 * 60; // 15 minutes
export const REFRESH_TOKEN_MAX_AGE = 7 * 24 * 60 * 60; // 7 days

// Short-lived project link token window — blueprint §4.1 Phase 3.
export const LINK_TOKEN_TTL_SECONDS = 15 * 60;

/** Downstream FastAPI base URL. Server-side only. */
export const FASTAPI_BASE_URL =
  process.env.FASTAPI_BASE_URL ?? "http://localhost:8000";

/** Access-token signing secret (shared with FastAPI). */
export const JWT_SECRET = process.env.JWT_SECRET ?? "";

/** Redis connection string for the SSE gateway. */
export const REDIS_URL = process.env.REDIS_URL ?? "redis://localhost:6379/0";

export const IS_PRODUCTION = process.env.NODE_ENV === "production";

/** Downstream FastAPI endpoint paths (BFF → backend mapping). */
export const BACKEND_ROUTES = {
  login: "/auth/login",
  register: "/auth/register",
  refresh: "/auth/refresh",
  projects: "/projects",
  projectLink: "/projects/link",
} as const;

/**
 * Fail fast in server contexts if a required secret is missing. Call this from
 * Node route handlers (not the edge middleware, which only reads JWT_SECRET).
 */
export function assertServerEnv(): void {
  const missing: string[] = [];
  if (!JWT_SECRET) missing.push("JWT_SECRET");
  if (!process.env.FASTAPI_BASE_URL) missing.push("FASTAPI_BASE_URL");
  if (missing.length > 0) {
    throw new Error(
      `Missing required environment variables: ${missing.join(", ")} (§7.3).`,
    );
  }
}
