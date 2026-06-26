/**
 * GET /api/projects/[projectId]/documents/[docId]/download
 *
 * Binary passthrough — authenticates the session and streams the file back from
 * FastAPI (which reads it from MinIO), preserving content-type. Not the JSON
 * `proxy` helper since this returns bytes.
 */

import type { NextRequest } from "next/server";

import { requireSession } from "@/lib/auth";
import { FASTAPI_BASE_URL, backendPath } from "@/lib/env";
import { errorJson } from "@/lib/responses";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _req: NextRequest,
  { params }: { params: { projectId: string; docId: string } },
) {
  const auth = await requireSession();
  if ("response" in auth) return auth.response;

  try {
    const upstream = await fetch(
      `${FASTAPI_BASE_URL}${backendPath.documentDownload(params.projectId, params.docId)}`,
      { headers: { Authorization: `Bearer ${auth.accessToken}` }, cache: "no-store" },
    );
    if (!upstream.ok || !upstream.body) {
      return errorJson(upstream.status === 404 ? 404 : 502, "download_failed");
    }
    return new Response(upstream.body, {
      status: 200,
      headers: {
        "Content-Type":
          upstream.headers.get("content-type") ?? "application/octet-stream",
        "Content-Disposition":
          upstream.headers.get("content-disposition") ?? "inline",
        "Cache-Control": "private, no-store",
      },
    });
  } catch (err) {
    console.error("[documents/download] error:", err);
    return errorJson(502, "download_failed");
  }
}
