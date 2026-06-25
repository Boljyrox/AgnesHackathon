/**
 * POST /api/auth/refresh
 *
 * Silent token rotation (§6.2). Reads the refresh token from the httpOnly
 * cookie, asks FastAPI to verify + rotate it, and atomically rewrites BOTH
 * cookies (rotating the refresh token defends against replay). On any failure
 * the session cookies are cleared and 401 is returned.
 *
 * Called both directly by the client (silent refresh) and by the edge
 * middleware (which forwards the cookie header).
 */

import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { backendJson, BackendError } from "@/lib/backend";
import { accessCookie, clearedCookies, refreshCookie } from "@/lib/cookies";
import { BACKEND_ROUTES, COOKIE_NAMES, assertServerEnv } from "@/lib/env";
import { errorJson, withCookies } from "@/lib/responses";
import type { BackendTokenPair } from "@/lib/types";

export const runtime = "nodejs";

export async function POST(): Promise<NextResponse> {
  try {
    assertServerEnv();

    const jar = await cookies();
    const refreshToken = jar.get(COOKIE_NAMES.refresh)?.value;
    if (!refreshToken) {
      return errorJson(401, "no_refresh_token");
    }

    const tokens = await backendJson<BackendTokenPair>({
      method: "POST",
      path: BACKEND_ROUTES.refresh,
      // The refresh token is verified by FastAPI (it holds JWT_REFRESH_SECRET).
      body: { refresh_token: refreshToken },
    });

    const response = NextResponse.json({ ok: true }, { status: 200 });
    return withCookies(response, [
      accessCookie(tokens.access_token),
      refreshCookie(tokens.refresh_token),
    ]);
  } catch (err) {
    if (err instanceof BackendError && (err.status === 401 || err.status === 403)) {
      // Refresh token invalid/expired/revoked — clear the session.
      const response = errorJson(401, "refresh_rejected");
      return withCookies(response, clearedCookies());
    }
    if (err instanceof BackendError) {
      return errorJson(502, "upstream_error");
    }
    console.error("[auth/refresh] unexpected error:", err);
    return errorJson(500, "internal_error");
  }
}
