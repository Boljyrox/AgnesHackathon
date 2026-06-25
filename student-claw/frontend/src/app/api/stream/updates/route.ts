/**
 * GET /api/stream/updates — Server-Sent Events gateway (blueprint §4.2).
 *
 * Opens a long-lived text/event-stream per authenticated session. A dedicated
 * Redis subscriber listens on `project_updates:{project_id}` for every project
 * the user belongs to; messages published by the AI tool executors (and the
 * bot) are forwarded to the browser immediately. A 30s heartbeat keeps
 * intermediaries from tearing down the idle connection, and both the Redis
 * client and heartbeat are torn down when the connection drops.
 */

import Redis from "ioredis";
import { NextResponse } from "next/server";

import { requireSession } from "@/lib/auth";
import { REDIS_URL } from "@/lib/env";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const HEARTBEAT_MS = 30_000;

export async function GET(req: Request): Promise<Response> {
  const auth = await requireSession();
  if ("response" in auth) return auth.response as NextResponse;

  const channels = auth.session.project_ids.map((id) => `project_updates:${id}`);
  const encoder = new TextEncoder();

  let controller: ReadableStreamDefaultController<Uint8Array> | null = null;
  let subscriber: Redis | null = null;
  let heartbeat: ReturnType<typeof setInterval> | null = null;
  let closed = false;

  const send = (chunk: string): void => {
    if (closed || controller === null) return;
    try {
      controller.enqueue(encoder.encode(chunk));
    } catch {
      // Controller already closed; ignore.
    }
  };

  const cleanup = (): void => {
    if (closed) return;
    closed = true;
    if (heartbeat) clearInterval(heartbeat);
    if (subscriber) {
      subscriber.removeAllListeners();
      // quit() flushes; disconnect() as a hard fallback.
      subscriber.quit().catch(() => subscriber?.disconnect());
      subscriber = null;
    }
    try {
      controller?.close();
    } catch {
      // Already closed.
    }
  };

  const stream = new ReadableStream<Uint8Array>({
    async start(ctrl) {
      controller = ctrl;

      // Open the stream + advise the browser's EventSource reconnect interval.
      send(": connected\n\n");
      send("retry: 5000\n\n");

      subscriber = new Redis(REDIS_URL, {
        lazyConnect: true,
        maxRetriesPerRequest: null,
      });

      subscriber.on("message", (_channel: string, message: string) => {
        // `message` is the JSON payload published by the backend (single line).
        send(`event: project_update\ndata: ${message}\n\n`);
      });
      subscriber.on("error", (err: Error) => {
        console.error("[sse] redis error:", err.message);
      });

      try {
        await subscriber.connect();
        if (channels.length > 0) {
          await subscriber.subscribe(...channels);
        }
      } catch (err) {
        console.error("[sse] failed to subscribe:", err);
        cleanup();
        return;
      }

      heartbeat = setInterval(() => send(": heartbeat\n\n"), HEARTBEAT_MS);

      // Client navigated away / connection dropped.
      req.signal.addEventListener("abort", cleanup);
    },
    cancel() {
      cleanup();
    },
  });

  return new Response(stream, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      // Disable proxy buffering (nginx) so events flush in real time.
      "X-Accel-Buffering": "no",
    },
  });
}
