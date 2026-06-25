/** Shared TypeScript contracts for the BFF gateway. */

/** Decoded access-JWT payload (blueprint §6.2). */
export interface SessionPayload {
  sub: string; // student UUID
  username: string;
  telegram_verified: boolean;
  project_ids: string[];
  iat: number;
  exp: number;
}

/** Token pair returned by FastAPI auth endpoints. */
export interface BackendTokenPair {
  access_token: string;
  refresh_token: string;
}

/** Project summary surfaced to the dashboard. */
export interface ProjectSummary {
  id: string;
  name: string;
  module_code: string | null;
  status: "active" | "archived" | "cleared" | "clearing";
  role: "member" | "lead" | "observer";
  qdrant_point_count: number;
}

/** Response of POST /api/projects/link (Phase 3). */
export interface ProjectLinkResponse {
  verification_required: true;
  token: string;
  expires_at: string; // ISO 8601
  instructions: string;
}

/** Standard error envelope returned to the client. */
export interface ApiError {
  error: string;
  message?: string;
}
