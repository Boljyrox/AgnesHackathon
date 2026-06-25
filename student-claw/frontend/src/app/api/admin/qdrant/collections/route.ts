/** GET /api/admin/qdrant/collections — list Qdrant collections (admin-gated). */

import { adminBackendPath } from "@/lib/env";
import { adminProxy } from "@/lib/adminProxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return adminProxy({ method: "GET", path: adminBackendPath.collections() });
}
