/** PATCH /api/projects/[projectId]/tasks/[taskId] — update task status (proxied). */

import type { NextRequest } from "next/server";

import { backendPath } from "@/lib/env";
import { proxy } from "@/lib/proxy";

export const runtime = "nodejs";

export async function PATCH(
  req: NextRequest,
  { params }: { params: { projectId: string; taskId: string } },
) {
  const body = await req.json().catch(() => ({}));
  return proxy({
    method: "PATCH",
    path: backendPath.task(params.projectId, params.taskId),
    body,
  });
}
