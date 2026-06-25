/** POST /api/projects/[projectId]/context — RAG Q&A (proxied to the agent). */

import type { NextRequest } from "next/server";

import { backendPath } from "@/lib/env";
import { proxy } from "@/lib/proxy";

export const runtime = "nodejs";

export async function POST(
  req: NextRequest,
  { params }: { params: { projectId: string } },
) {
  const body = await req.json().catch(() => ({}));
  return proxy({
    method: "POST",
    path: backendPath.context(params.projectId),
    body,
  });
}
