/**
 * OAuth2 PKCE + signed-state helpers for the Google Calendar flow (§6.5).
 *
 * The PKCE `code_verifier`, the CSRF `state`, and the student id are bundled
 * into a short-lived signed JWT stored in an httpOnly cookie. On callback we
 * verify the signature and match `state`, defeating CSRF and code-injection.
 */

import { createHash, randomBytes } from "node:crypto";

import { SignJWT, jwtVerify } from "jose";

import { OAUTH_COOKIE_SECRET, OAUTH_STATE_TTL_SECONDS } from "@/lib/env";

export interface OAuthStatePayload {
  state: string;
  codeVerifier: string;
  sub: string; // student id
}

function base64url(buf: Buffer): string {
  return buf.toString("base64url");
}

/** Generate a PKCE verifier + S256 challenge pair. */
export function generatePkce(): { verifier: string; challenge: string } {
  const verifier = base64url(randomBytes(32)); // 43-char base64url
  const challenge = base64url(createHash("sha256").update(verifier).digest());
  return { verifier, challenge };
}

export function generateState(): string {
  return randomBytes(32).toString("hex");
}

function secret(): Uint8Array {
  if (!OAUTH_COOKIE_SECRET) {
    throw new Error("OAUTH_COOKIE_SECRET (or JWT_SECRET) is not configured.");
  }
  return new TextEncoder().encode(OAUTH_COOKIE_SECRET);
}

/** Sign the OAuth state bundle into a short-lived JWT for the cookie. */
export async function signOAuthState(payload: OAuthStatePayload): Promise<string> {
  return new SignJWT({ ...payload })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(`${OAUTH_STATE_TTL_SECONDS}s`)
    .sign(secret());
}

/** Verify + decode the OAuth state cookie. Returns null if invalid/expired. */
export async function verifyOAuthState(
  token: string | undefined,
): Promise<OAuthStatePayload | null> {
  if (!token) return null;
  try {
    const { payload } = await jwtVerify(token, secret(), { algorithms: ["HS256"] });
    if (
      typeof payload.state === "string" &&
      typeof payload.codeVerifier === "string" &&
      typeof payload.sub === "string"
    ) {
      return {
        state: payload.state,
        codeVerifier: payload.codeVerifier,
        sub: payload.sub,
      };
    }
    return null;
  } catch {
    return null;
  }
}
