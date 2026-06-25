/**
 * Thin, typed client for the downstream FastAPI service.
 *
 * Centralises base-URL resolution, JSON handling, and a 10s timeout. Errors are
 * normalised into `BackendError` so route handlers can map them to clean client
 * responses without ever leaking downstream internals.
 */

import { FASTAPI_BASE_URL } from "@/lib/env";

export class BackendError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly upstreamBody?: unknown,
  ) {
    super(message);
    this.name = "BackendError";
  }
}

interface BackendRequest {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  path: string;
  /** JSON body to send. */
  body?: unknown;
  /** Bearer token to forward (the user's access JWT). */
  bearer?: string;
  /** Per-request timeout in ms (default 10s). */
  timeoutMs?: number;
}

/**
 * Perform a JSON request against FastAPI and parse the response.
 * Throws `BackendError` for non-2xx responses or transport failures.
 */
export async function backendJson<T>(req: BackendRequest): Promise<T> {
  const { method = "GET", path, body, bearer, timeoutMs = 10_000 } = req;

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (bearer) headers["Authorization"] = `Bearer ${bearer}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(`${FASTAPI_BASE_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
      cache: "no-store",
    });
  } catch (err) {
    throw new BackendError(
      502,
      err instanceof Error && err.name === "AbortError"
        ? "Upstream request timed out."
        : "Upstream service unavailable.",
    );
  } finally {
    clearTimeout(timer);
  }

  const text = await res.text();
  const parsed: unknown = text ? safeJson(text) : undefined;

  if (!res.ok) {
    const message =
      (parsed as { detail?: string; message?: string } | undefined)?.detail ??
      (parsed as { message?: string } | undefined)?.message ??
      `Upstream error (${res.status}).`;
    throw new BackendError(res.status, message, parsed);
  }

  return parsed as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}
