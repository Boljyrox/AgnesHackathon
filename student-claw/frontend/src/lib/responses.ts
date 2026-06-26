/**
 * Response construction helpers shared by route handlers.
 */

import { NextResponse } from "next/server";

import type { CookieSpec } from "@/lib/cookies";
import type { ApiError } from "@/lib/types";

/** Attach a set of cookie specs to a response (mutates + returns it). */
export function withCookies<T>(
  response: NextResponse<T>,
  specs: CookieSpec[],
): NextResponse<T> {
  for (const spec of specs) {
    response.cookies.set(spec.name, spec.value, spec.options);
  }
  return response;
}

/** Standard JSON error response with a sanitized envelope. */
export function errorJson(
  status: number,
  error: string,
  message?: string,
): NextResponse<ApiError> {
  return NextResponse.json<ApiError>({ error, ...(message ? { message } : {}) }, { status });
}
