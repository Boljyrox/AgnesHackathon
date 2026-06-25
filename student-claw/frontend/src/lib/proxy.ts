/**
 * Generic authenticated proxy from a BFF route to FastAPI.
 *
 * Authenticates the session, forwards the access JWT as a Bearer, and maps
 * known client-error statuses through verbatim while masking everything else as
 * a generic upstream error (no internal leakage).
 */

import { NextResponse } from "next/server";

import { requireSession } from "@/lib/auth";
import { backendJson, BackendError } from "@/lib/backend";
import { errorJson } from "@/lib/responses";

const PASSTHROUGH = new Set([400, 401, 403, 404, 409, 422]);

export async function proxy(opts: {
  method: "GET" | "POST" | "PATCH" | "DELETE";
  path: string;
  body?: unknown;
}): Promise<NextResponse> {
  const auth = await requireSession();
  if ("response" in auth) return auth.response;

  try {
    const data = await backendJson<unknown>({
      method: opts.method,
      path: opts.path,
      bearer: auth.accessToken,
      body: opts.body,
    });
    return NextResponse.json(data ?? { ok: true });
  } catch (err) {
    if (err instanceof BackendError) {
      const status = PASSTHROUGH.has(err.status) ? err.status : 502;
      return errorJson(
        status,
        status === 502 ? "upstream_error" : "request_failed",
        status === 502 ? undefined : err.message,
      );
    }
    console.error("[proxy] unexpected error:", err);
    return errorJson(500, "internal_error");
  }
}
