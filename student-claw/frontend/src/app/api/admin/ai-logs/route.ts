/** GET /api/admin/ai-logs — Agnes AI request logs (admin-gated proxy). */

import type { NextRequest } from "next/server";

import { adminBackendPath } from "@/lib/env";
import { adminProxy } from "@/lib/adminProxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const qs = req.nextUrl.search; // forward ?chat_id, ?kind, ?limit, ?offset
  return adminProxy({ method: "GET", path: `${adminBackendPath.aiLogs()}${qs}` });
}
