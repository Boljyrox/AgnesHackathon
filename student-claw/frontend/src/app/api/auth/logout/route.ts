/**
 * POST /api/auth/logout
 *
 * Clears the session cookies and redirects to /login. Stateless on our side;
 * the (short-lived) access token simply expires, and the refresh token is
 * dropped from the browser.
 */

import { NextResponse } from "next/server";

import { clearedCookies } from "@/lib/cookies";
import { withCookies } from "@/lib/responses";

export const runtime = "nodejs";

export async function POST(req: Request): Promise<NextResponse> {
  const response = NextResponse.redirect(new URL("/login", req.url), {
    status: 303, // force a GET on the redirect target
  });
  return withCookies(response, clearedCookies());
}
