/** POST /api/projects/[projectId]/clearcache — cache cleanse (lead-only, proxied). */

import type { NextRequest } from "next/server";

import { backendPath } from "@/lib/env";
import { proxy } from "@/lib/proxy";

export const runtime = "nodejs";

export async function POST(
  req: NextRequest,
  { params }: { params: { projectId: string } },
) {
  const body = await req.json().catch(() => ({ include_files: false }));
  return proxy({
    method: "POST",
    path: backendPath.clearcache(params.projectId),
    body,
  });
}
