/** GET /api/admin/qdrant/[chatId]/points — inspect stored vectors (admin-gated). */

import type { NextRequest } from "next/server";

import { adminBackendPath } from "@/lib/env";
import { adminProxy } from "@/lib/adminProxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  req: NextRequest,
  { params }: { params: { chatId: string } },
) {
  const qs = req.nextUrl.search; // forward ?limit
  return adminProxy({
    method: "GET",
    path: `${adminBackendPath.points(params.chatId)}${qs}`,
  });
}
