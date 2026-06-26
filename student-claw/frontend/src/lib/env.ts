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

// ---- Google Calendar OAuth2 (blueprint §6.5) ----
export const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID ?? "";
export const GOOGLE_CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET ?? "";
export const GOOGLE_REDIRECT_URI =
  process.env.GOOGLE_REDIRECT_URI ??
  "http://localhost:3000/api/integrations/google/callback";
export const GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth";
export const GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token";
export const GOOGLE_CALENDAR_SCOPE =
  "https://www.googleapis.com/auth/calendar.events";

/** AES-256-GCM key (hex or base64, 32 bytes) — shared with FastAPI. */
export const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY ?? "";

/** Secret used to sign the short-lived PKCE/state OAuth cookie. */
export const OAUTH_COOKIE_SECRET =
  process.env.OAUTH_COOKIE_SECRET ?? process.env.JWT_SECRET ?? "";

export const OAUTH_COOKIE_NAME = "g_oauth";
export const OAUTH_STATE_TTL_SECONDS = 10 * 60; // 10 minutes

// ---- SUTD_Admin dashboard (Requirement 1) ----
/** Shared admin token (must match the FastAPI ADMIN_API_TOKEN). Server-only. */
export const ADMIN_API_TOKEN = process.env.ADMIN_API_TOKEN ?? "";
export const ADMIN_COOKIE_NAME = "sutd_admin";
export const ADMIN_COOKIE_TTL_SECONDS = 8 * 60 * 60; // 8 hours

export const adminBackendPath = {
  aiLogs: () => `/admin/ai-logs`,
  collections: () => `/admin/qdrant/collections`,
  points: (chatId: string) => `/admin/qdrant/${chatId}/points`,
} as const;

/** Downstream FastAPI endpoint paths (BFF → backend mapping). */
export const BACKEND_ROUTES = {
  login: "/auth/login",
  register: "/auth/register",
  refresh: "/auth/refresh",
  projects: "/projects",
  projectLink: "/projects/link",
  googleCalendar: "/students/me/google-calendar",
} as const;

/** Parameterised backend paths for project sub-resources. */
export const backendPath = {
  overview: () => `/me/overview`,
  project: (projectId: string) => `/projects/${projectId}`,
  tasks: (projectId: string) => `/projects/${projectId}/tasks`,
  task: (projectId: string, taskId: string) =>
    `/projects/${projectId}/tasks/${taskId}`,
  members: (projectId: string) => `/projects/${projectId}/members`,
  documents: (projectId: string) => `/projects/${projectId}/documents`,
  documentDownload: (projectId: string, docId: string) =>
    `/projects/${projectId}/documents/${docId}/download`,
  context: (projectId: string) => `/projects/${projectId}/context`,
  deadlines: (projectId: string) => `/projects/${projectId}/deadlines`,
  contributions: (projectId: string) => `/projects/${projectId}/contributions`,
  clearcache: (projectId: string) => `/projects/${projectId}/clearcache`,
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
