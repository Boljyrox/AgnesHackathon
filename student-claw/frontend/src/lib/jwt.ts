/**
 * Edge-compatible JWT verification using `jose` (Web Crypto under the hood).
 *
 * Only the ACCESS token is verified here — the middleware and route handlers
 * need to read its claims. The REFRESH token is opaque to Next.js; only
 * FastAPI (which holds JWT_REFRESH_SECRET) verifies and rotates it.
 */

import { jwtVerify, type JWTPayload } from "jose";

import { JWT_SECRET } from "@/lib/env";
import type { SessionPayload } from "@/lib/types";

let cachedSecret: Uint8Array | null = null;

function accessSecret(): Uint8Array {
  if (!JWT_SECRET) {
    throw new Error("JWT_SECRET is not configured.");
  }
  if (cachedSecret === null) {
    cachedSecret = new TextEncoder().encode(JWT_SECRET);
  }
  return cachedSecret;
}

function isSessionPayload(p: JWTPayload): p is JWTPayload & SessionPayload {
  return (
    typeof p.sub === "string" &&
    typeof (p as Record<string, unknown>).username === "string" &&
    Array.isArray((p as Record<string, unknown>).project_ids)
  );
}

/**
 * Verify the access token's signature + expiry. Returns the typed payload, or
 * `null` for any invalid/expired/malformed token (never throws on bad input).
 */
export async function verifyAccessToken(
  token: string | undefined,
): Promise<SessionPayload | null> {
  if (!token) return null;
  try {
    const { payload } = await jwtVerify(token, accessSecret(), {
      algorithms: ["HS256"],
    });
    if (!isSessionPayload(payload)) return null;
    return {
      sub: payload.sub as string,
      username: payload.username,
      telegram_verified: Boolean(payload.telegram_verified),
      project_ids: payload.project_ids,
      iat: payload.iat ?? 0,
      exp: payload.exp ?? 0,
    };
  } catch {
    // Signature failure, expiry, malformed token — all treated as unauthenticated.
    return null;
  }
}
