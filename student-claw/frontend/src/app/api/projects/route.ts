/**
 * GET /api/projects
 *
 * Returns the authenticated user's projects. The BFF reads the session from the
 * httpOnly cookie and forwards the access JWT as a Bearer to FastAPI, which
 * scopes the query to the student's memberships (absolute tenant isolation).
 */

import { NextResponse } from "next/server";

import { requireSession } from "@/lib/auth";
import { backendJson, BackendError } from "@/lib/backend";
import { BACKEND_ROUTES } from "@/lib/env";
import { errorJson } from "@/lib/responses";
import type { ProjectSummary } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  const auth = await requireSession();
  if ("response" in auth) return auth.response;

  try {
    const projects = await backendJson<ProjectSummary[]>({
      method: "GET",
      path: BACKEND_ROUTES.projects,
      bearer: auth.accessToken,
    });
    return NextResponse.json({ projects }, { status: 200 });
  } catch (err) {
    if (err instanceof BackendError) {
      if (err.status === 401) return errorJson(401, "unauthorized");
      return errorJson(502, "upstream_error");
    }
    console.error("[projects:GET] unexpected error:", err);
    return errorJson(500, "internal_error");
  }
}
