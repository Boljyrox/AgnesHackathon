/**
 * Global route middleware (blueprint §6.2) — runs on the Edge runtime.
 *
 * Flow for every protected request:
 *   1. Validate the access JWT from cookies. Valid → continue.
 *   2. Expired/missing but a refresh cookie exists → silently call the rotation
 *      endpoint (/api/auth/refresh), forward the new Set-Cookie headers, and
 *      continue to the original destination.
 *   3. Otherwise → 401 (for /api/* requests) or redirect to /login with a
 *      `returnUrl` (for page navigations).
 *
 * Public route groups — (auth) pages and /api/auth/* — are excluded via the
 * matcher, so the refresh fetch below never recurses through middleware.
 */

import { NextResponse, type NextRequest } from "next/server";

import { COOKIE_NAMES } from "@/lib/env";
import { verifyAccessToken } from "@/lib/jwt";

function isApiRequest(pathname: string): boolean {
  return pathname.startsWith("/api/");
}

/** Read all Set-Cookie headers (getSetCookie isn't in the DOM lib types yet). */
function readSetCookies(headers: Headers): string[] {
  const h = headers as Headers & { getSetCookie?: () => string[] };
  if (typeof h.getSetCookie === "function") return h.getSetCookie();
  const single = headers.get("set-cookie");
  return single ? [single] : [];
}

function unauthenticatedResponse(req: NextRequest): NextResponse {
  const { pathname, search } = req.nextUrl;
  if (isApiRequest(pathname)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const loginUrl = new URL("/login", req.url);
  loginUrl.searchParams.set("returnUrl", `${pathname}${search}`);
  return NextResponse.redirect(loginUrl);
}

export async function middleware(req: NextRequest): Promise<NextResponse> {
  const accessToken = req.cookies.get(COOKIE_NAMES.access)?.value;
  const session = await verifyAccessToken(accessToken);

  // 1) Valid access token — proceed.
  if (session) {
    return NextResponse.next();
  }

  // 2) No valid access token, but a refresh token exists — attempt rotation.
  const refreshToken = req.cookies.get(COOKIE_NAMES.refresh)?.value;
  if (!refreshToken) {
    return unauthenticatedResponse(req);
  }

  try {
    const refreshRes = await fetch(new URL("/api/auth/refresh", req.url), {
      method: "POST",
      headers: {
        // Forward the cookie jar so the refresh route can read refresh_token.
        cookie: req.headers.get("cookie") ?? "",
      },
    });

    if (!refreshRes.ok) {
      return unauthenticatedResponse(req);
    }

    // Propagate the rotated cookies onto the continuing response.
    const response = NextResponse.next();
    for (const cookie of readSetCookies(refreshRes.headers)) {
      response.headers.append("set-cookie", cookie);
    }
    return response;
  } catch {
    // Rotation transport failure — treat as unauthenticated, never 500 the page.
    return unauthenticatedResponse(req);
  }
}

export const config = {
  // Protected surfaces only. (auth) pages and /api/auth/* are intentionally absent.
  matcher: [
    "/", // dashboard overview root
    "/projects/:path*",
    "/settings/:path*",
    "/notifications/:path*",
    "/api/projects/:path*",
    "/api/stream/:path*",
  ],
};
