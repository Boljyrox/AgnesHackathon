/**
 * POST /api/auth/register
 *
 * Phase 1 of onboarding (§4.1). Forwards the new-account payload to FastAPI
 * (which hashes the password with bcrypt and inserts the student row with a
 * NULL telegram_user_id), then sets the returned JWT pair as session cookies.
 */

import { NextResponse } from "next/server";
import { z } from "zod";

import { backendJson, BackendError } from "@/lib/backend";
import { accessCookie, refreshCookie } from "@/lib/cookies";
import { BACKEND_ROUTES, assertServerEnv } from "@/lib/env";
import { errorJson, withCookies } from "@/lib/responses";
import type { BackendTokenPair } from "@/lib/types";

export const runtime = "nodejs";

const RegisterSchema = z.object({
  display_name: z.string().min(1).max(100),
  username: z.string().min(3).max(50).regex(/^[a-zA-Z0-9_]+$/, "alphanumeric/underscore only"),
  password: z.string().min(8).max(256),
  // Stored without the leading "@" (blueprint §2.3).
  telegram_username: z
    .string()
    .max(50)
    .transform((s) => s.replace(/^@/, ""))
    .optional(),
});

export async function POST(req: Request): Promise<NextResponse> {
  try {
    assertServerEnv();

    const body = await req.json().catch(() => null);
    const parsed = RegisterSchema.safeParse(body);
    if (!parsed.success) {
      return errorJson(
        400,
        "invalid_request",
        parsed.error.issues[0]?.message ?? "Invalid registration details.",
      );
    }

    const tokens = await backendJson<BackendTokenPair>({
      method: "POST",
      path: BACKEND_ROUTES.register,
      body: parsed.data,
    });

    const response = NextResponse.json({ ok: true }, { status: 201 });
    return withCookies(response, [
      accessCookie(tokens.access_token),
      refreshCookie(tokens.refresh_token),
    ]);
  } catch (err) {
    if (err instanceof BackendError) {
      // 409 = username/email/telegram already taken.
      if (err.status === 409) {
        return errorJson(409, "conflict", "That username or Telegram handle is already in use.");
      }
      if (err.status === 400) {
        return errorJson(400, "invalid_request", "Invalid registration details.");
      }
      return errorJson(502, "upstream_error");
    }
    console.error("[auth/register] unexpected error:", err);
    return errorJson(500, "internal_error");
  }
}
