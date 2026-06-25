/** GET + PATCH /api/projects/[projectId] — project detail + goals (proxied). */

import type { NextRequest } from "next/server";

import { backendPath } from "@/lib/env";
import { proxy } from "@/lib/proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _req: NextRequest,
  { params }: { params: { projectId: string } },
) {
  return proxy({ method: "GET", path: backendPath.project(params.projectId) });
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: { projectId: string } },
) {
  const body = await req.json().catch(() => ({}));
  return proxy({ method: "PATCH", path: backendPath.project(params.projectId), body });
}
