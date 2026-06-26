/** GET /api/projects/[projectId]/documents — list shared files (proxied). */

import type { NextRequest } from "next/server";

import { backendPath } from "@/lib/env";
import { proxy } from "@/lib/proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _req: NextRequest,
  { params }: { params: { projectId: string } },
) {
  return proxy({ method: "GET", path: backendPath.documents(params.projectId) });
}
