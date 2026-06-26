/**
 * GET /api/integrations/google/connect  (blueprint §6.5)
 *
 * Begins the Google Calendar OAuth2 flow:
 *   1. Authenticate the session.
 *   2. Generate a PKCE verifier/challenge + a random CSRF state.
 *   3. Stash {state, codeVerifier, sub} in a short-lived signed httpOnly cookie
 *      (SameSite=Lax so it survives Google's top-level redirect back).
 *   4. Redirect to Google's consent screen requesting calendar.events with
 *      offline access and forced consent (to guarantee a refresh_token).
 */

import { NextResponse } from "next/server";

import { getSession } from "@/lib/auth";
import {
  GOOGLE_AUTH_URI,
  GOOGLE_CALENDAR_SCOPE,
  GOOGLE_CLIENT_ID,
  GOOGLE_REDIRECT_URI,
  IS_PRODUCTION,
  OAUTH_COOKIE_NAME,
  OAUTH_STATE_TTL_SECONDS,
} from "@/lib/env";
import { generatePkce, generateState, signOAuthState } from "@/lib/oauth";

export const runtime = "nodejs";

export async function GET(req: Request): Promise<NextResponse> {
  const auth = await getSession();
  if (!auth) {
    const loginUrl = new URL("/login", req.url);
    loginUrl.searchParams.set("returnUrl", "/settings/integrations");
    return NextResponse.redirect(loginUrl);
  }

  if (!GOOGLE_CLIENT_ID) {
    return NextResponse.redirect(
      new URL("/settings/integrations?status=misconfigured", req.url),
    );
  }

  const { verifier, challenge } = generatePkce();
  const state = generateState();
  const cookieValue = await signOAuthState({
    state,
    codeVerifier: verifier,
    sub: auth.session.sub,
  });

  const authUrl = new URL(GOOGLE_AUTH_URI);
  authUrl.searchParams.set("client_id", GOOGLE_CLIENT_ID);
  authUrl.searchParams.set("redirect_uri", GOOGLE_REDIRECT_URI);
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("scope", GOOGLE_CALENDAR_SCOPE);
  authUrl.searchParams.set("access_type", "offline");
  authUrl.searchParams.set("prompt", "consent"); // force refresh_token issuance
  authUrl.searchParams.set("include_granted_scopes", "true");
  authUrl.searchParams.set("code_challenge", challenge);
  authUrl.searchParams.set("code_challenge_method", "S256");
  authUrl.searchParams.set("state", state);

  const response = NextResponse.redirect(authUrl);
  response.cookies.set(OAUTH_COOKIE_NAME, cookieValue, {
    httpOnly: true,
    secure: IS_PRODUCTION,
    // Lax (not Strict): the cookie must accompany Google's cross-site redirect.
    sameSite: "lax",
    path: "/api/integrations/google",
    maxAge: OAUTH_STATE_TTL_SECONDS,
  });
  return response;
}
