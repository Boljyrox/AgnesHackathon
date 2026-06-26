/** GET /api/me/overview — home dashboard aggregate (proxied). */

import { backendPath } from "@/lib/env";
import { proxy } from "@/lib/proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return proxy({ method: "GET", path: backendPath.overview() });
}
