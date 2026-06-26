/**
 * Admin-gated proxy to FastAPI (SUTD_Admin).
 *
 * Verifies the httpOnly `sutd_admin` cookie equals ADMIN_API_TOKEN (server-side,
 * constant-time), then forwards the request to FastAPI with the X-Admin-Token
 * header. The admin token therefore never reaches client JavaScript.
 */

import { timingSafeEqual } from "node:crypto";

import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  ADMIN_API_TOKEN,
  ADMIN_COOKIE_NAME,
  FASTAPI_BASE_URL,
} from "@/lib/env";
import { errorJson } from "@/lib/responses";

function tokenOk(provided: string | undefined): boolean {
  if (!ADMIN_API_TOKEN || !provided) return false;
  const a = Buffer.from(provided);
  const b = Buffer.from(ADMIN_API_TOKEN);
  return a.length === b.length && timingSafeEqual(a, b);
}

export async function isAdminAuthed(): Promise<boolean> {
  const jar = await cookies();
  return tokenOk(jar.get(ADMIN_COOKIE_NAME)?.value);
}

export async function adminProxy(opts: {
  method: "GET" | "POST";
  path: string;
}): Promise<NextResponse> {
  if (!(await isAdminAuthed())) {
    return errorJson(401, "admin_unauthorized");
  }

  try {
    const res = await fetch(`${FASTAPI_BASE_URL}${opts.path}`, {
      method: opts.method,
      headers: { Accept: "application/json", "X-Admin-Token": ADMIN_API_TOKEN },
      cache: "no-store",
    });
    const text = await res.text();
    const data: unknown = text ? JSON.parse(text) : {};
    if (!res.ok) {
      return errorJson(res.status === 403 ? 403 : 502, "upstream_error");
    }
    return NextResponse.json(data);
  } catch (err) {
    console.error("[adminProxy] error:", err);
    return errorJson(502, "upstream_error");
  }
}
