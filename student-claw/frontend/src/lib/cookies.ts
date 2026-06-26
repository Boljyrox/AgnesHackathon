/**
 * httpOnly session-cookie helpers (blueprint §6.2).
 *
 * Tokens live exclusively in `httpOnly`, `Secure`, `SameSite=Strict` cookies so
 * client-side JavaScript can never read them (XSS-resistant) and they are not
 * sent on cross-site requests (CSRF-resistant). Edge-safe: returns plain option
 * objects compatible with both `NextResponse.cookies` and `cookies()`.
 */

import {
  ACCESS_TOKEN_MAX_AGE,
  COOKIE_NAMES,
  IS_PRODUCTION,
  REFRESH_TOKEN_MAX_AGE,
} from "@/lib/env";

/**
 * Structural subset of Next's `ResponseCookie` options accepted by both
 * `NextResponse.cookies.set(...)` and `cookies().set(...)`. Defined locally to
 * avoid depending on Next's compiled deep-import path.
 */
export interface CookieOptions {
  httpOnly?: boolean;
  secure?: boolean;
  sameSite?: "strict" | "lax" | "none";
  path?: string;
  maxAge?: number;
}

function baseOptions(maxAge: number): CookieOptions {
  return {
    httpOnly: true,
    secure: IS_PRODUCTION,
    sameSite: "strict",
    path: "/",
    maxAge,
  };
}

export interface CookieSpec {
  name: string;
  value: string;
  options: CookieOptions;
}

export function accessCookie(value: string): CookieSpec {
  return {
    name: COOKIE_NAMES.access,
    value,
    options: baseOptions(ACCESS_TOKEN_MAX_AGE),
  };
}

export function refreshCookie(value: string): CookieSpec {
  return {
    name: COOKIE_NAMES.refresh,
    value,
    options: baseOptions(REFRESH_TOKEN_MAX_AGE),
  };
}

/** Expired cookie specs used to clear the session on logout / auth failure. */
export function clearedCookies(): CookieSpec[] {
  const expire: CookieOptions = { ...baseOptions(0), maxAge: 0 };
  return [
    { name: COOKIE_NAMES.access, value: "", options: expire },
    { name: COOKIE_NAMES.refresh, value: "", options: expire },
  ];
}
