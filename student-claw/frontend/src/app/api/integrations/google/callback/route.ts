/**
 * GET /api/integrations/google/callback  (blueprint §6.5)
 *
 *   1. Verify the signed state cookie and match `state` (CSRF defence).
 *   2. Exchange the auth code (+ PKCE verifier) for tokens at Google.
 *   3. Isolate the refresh_token, encrypt it with AES-256-GCM.
 *   4. PATCH it to FastAPI (stored encrypted at rest, keyed to the student).
 *   5. Clear the OAuth cookie and redirect back to the integrations page.
 */

import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { getSession } from "@/lib/auth";
import { backendJson, BackendError } from "@/lib/backend";
import { encryptSecret } from "@/lib/crypto";
import {
  BACKEND_ROUTES,
  GOOGLE_CLIENT_ID,
  GOOGLE_CLIENT_SECRET,
  GOOGLE_REDIRECT_URI,
  GOOGLE_TOKEN_URI,
  OAUTH_COOKIE_NAME,
} from "@/lib/env";
import { verifyOAuthState } from "@/lib/oauth";

export const runtime = "nodejs";

function settingsRedirect(req: Request, status: string): NextResponse {
  const url = new URL("/settings/integrations", req.url);
  url.searchParams.set("status", status);
  const res = NextResponse.redirect(url);
  // Always clear the one-time OAuth cookie.
  res.cookies.set(OAUTH_COOKIE_NAME, "", {
    path: "/api/integrations/google",
    maxAge: 0,
  });
  return res;
}

interface GoogleTokenResponse {
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
  error?: string;
}

export async function GET(req: Request): Promise<NextResponse> {
  const url = new URL(req.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const oauthError = url.searchParams.get("error");

  if (oauthError) return settingsRedirect(req, "denied");
  if (!code || !state) return settingsRedirect(req, "invalid_response");

  // Verify the signed state cookie (CSRF + PKCE binding).
  const jar = await cookies();
  const stateCookie = await verifyOAuthState(jar.get(OAUTH_COOKIE_NAME)?.value);
  if (!stateCookie || stateCookie.state !== state) {
    return settingsRedirect(req, "csrf_failed");
  }

  // Confirm the same student is still signed in.
  const auth = await getSession();
  if (!auth || auth.session.sub !== stateCookie.sub) {
    return settingsRedirect(req, "session_mismatch");
  }

  // Exchange the code for tokens.
  let tokens: GoogleTokenResponse;
  try {
    const res = await fetch(GOOGLE_TOKEN_URI, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        code,
        client_id: GOOGLE_CLIENT_ID,
        client_secret: GOOGLE_CLIENT_SECRET,
        redirect_uri: GOOGLE_REDIRECT_URI,
        grant_type: "authorization_code",
        code_verifier: stateCookie.codeVerifier,
      }),
    });
    tokens = (await res.json()) as GoogleTokenResponse;
    if (!res.ok || tokens.error) {
      return settingsRedirect(req, "exchange_failed");
    }
  } catch {
    return settingsRedirect(req, "exchange_failed");
  }

  // Google only returns a refresh_token on first consent; we forced
  // prompt=consent so one should be present.
  if (!tokens.refresh_token) {
    return settingsRedirect(req, "no_refresh_token");
  }

  // Encrypt at rest and persist via FastAPI.
  try {
    const encrypted = encryptSecret(tokens.refresh_token);
    await backendJson<{ ok: true }>({
      method: "PATCH",
      path: BACKEND_ROUTES.googleCalendar,
      bearer: auth.accessToken,
      body: { encrypted_refresh_token: encrypted },
    });
  } catch (err) {
    if (err instanceof BackendError) return settingsRedirect(req, "store_failed");
    return settingsRedirect(req, "store_failed");
  }

  return settingsRedirect(req, "success");
}
