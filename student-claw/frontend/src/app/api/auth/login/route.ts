/**
 * POST /api/auth/login
 *
 * Forwards credentials to FastAPI, receives the JWT pair, and pins them into
 * httpOnly/Secure/SameSite=Strict cookies. The browser never sees the tokens.
 */

import { NextResponse } from "next/server";
import { z } from "zod";

import { backendJson, BackendError } from "@/lib/backend";
import { accessCookie, refreshCookie } from "@/lib/cookies";
import { BACKEND_ROUTES, assertServerEnv } from "@/lib/env";
import { errorJson, withCookies } from "@/lib/responses";
import type { BackendTokenPair } from "@/lib/types";

export const runtime = "nodejs";

const LoginSchema = z.object({
  username: z.string().min(1).max(50),
  password: z.string().min(1).max(256),
});

export async function POST(req: Request): Promise<NextResponse> {
  try {
    assertServerEnv();

    const body = await req.json().catch(() => null);
    const parsed = LoginSchema.safeParse(body);
    if (!parsed.success) {
      return errorJson(400, "invalid_request", "Username and password are required.");
    }

    const tokens = await backendJson<BackendTokenPair>({
      method: "POST",
      path: BACKEND_ROUTES.login,
      body: parsed.data,
    });

    const response = NextResponse.json({ ok: true }, { status: 200 });
    return withCookies(response, [
      accessCookie(tokens.access_token),
      refreshCookie(tokens.refresh_token),
    ]);
  } catch (err) {
    if (err instanceof BackendError) {
      // 401/400 from FastAPI → generic invalid-credentials message (no leakage).
      const status = err.status === 401 || err.status === 400 ? 401 : 502;
      return errorJson(
        status,
        status === 401 ? "invalid_credentials" : "upstream_error",
        status === 401 ? "Invalid username or password." : undefined,
      );
    }
    console.error("[auth/login] unexpected error:", err);
    return errorJson(500, "internal_error");
  }
}
