/** POST /api/admin/login — exchange the admin token for an httpOnly cookie. */

import { timingSafeEqual } from "node:crypto";

import { NextResponse } from "next/server";

import {
  ADMIN_API_TOKEN,
  ADMIN_COOKIE_NAME,
  ADMIN_COOKIE_TTL_SECONDS,
  IS_PRODUCTION,
} from "@/lib/env";
import { errorJson } from "@/lib/responses";

export const runtime = "nodejs";

export async function POST(req: Request): Promise<NextResponse> {
  if (!ADMIN_API_TOKEN) return errorJson(503, "admin_not_configured");

  const body = await req.json().catch(() => ({}));
  const token = typeof body?.token === "string" ? body.token : "";

  const a = Buffer.from(token);
  const b = Buffer.from(ADMIN_API_TOKEN);
  const ok = a.length === b.length && timingSafeEqual(a, b);
  if (!ok) return errorJson(401, "invalid_token", "Incorrect admin token.");

  const res = NextResponse.json({ ok: true });
  res.cookies.set(ADMIN_COOKIE_NAME, token, {
    httpOnly: true,
    secure: IS_PRODUCTION,
    sameSite: "strict",
    path: "/",
    maxAge: ADMIN_COOKIE_TTL_SECONDS,
  });
  return res;
}
