/**
 * Server-side session helpers for Node route handlers.
 *
 * Reads the access token from the httpOnly cookie jar, verifies it, and exposes
 * both the decoded session and the raw token (for forwarding as a Bearer to
 * FastAPI). Route handlers call `requireSession()` and get back a 401 response
 * to return directly if unauthenticated.
 */

import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { COOKIE_NAMES } from "@/lib/env";
import { verifyAccessToken } from "@/lib/jwt";
import type { ApiError, SessionPayload } from "@/lib/types";

export interface AuthenticatedSession {
  session: SessionPayload;
  accessToken: string;
}

/**
 * Resolve the current session from cookies. Returns `null` when no valid access
 * token is present (the middleware normally refreshes before we get here, but
 * handlers must still defend in depth).
 */
export async function getSession(): Promise<AuthenticatedSession | null> {
  const jar = await cookies();
  const accessToken = jar.get(COOKIE_NAMES.access)?.value;
  if (!accessToken) return null;
  const session = await verifyAccessToken(accessToken);
  if (!session) return null;
  return { session, accessToken };
}

/**
 * Guard helper: returns either the authenticated session or a ready-to-return
 * 401 JSON response. Usage:
 *
 *   const auth = await requireSession();
 *   if ("response" in auth) return auth.response;
 *   // auth.session, auth.accessToken are now available
 */
export async function requireSession(): Promise<
  AuthenticatedSession | { response: NextResponse<ApiError> }
> {
  const auth = await getSession();
  if (!auth) {
    return {
      response: NextResponse.json<ApiError>(
        { error: "unauthorized" },
        { status: 401 },
      ),
    };
  }
  return auth;
}
