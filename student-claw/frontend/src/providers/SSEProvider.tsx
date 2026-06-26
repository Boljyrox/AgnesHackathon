"use client";

/**
 * Real-time SSE context (blueprint §4.2, §6.3).
 *
 * Opens a single EventSource to /api/stream/updates for the whole dashboard.
 * Events published by the AI tool executors / bot arrive as `project_update`
 * events whose JSON body carries a discriminating `type` (e.g. "task_created",
 * "member_joined"). Components subscribe to a specific `type` via the
 * `useSSEEvent` hook; the provider fans the event out to matching listeners.
 *
 * The browser's EventSource auto-reconnects (the server also sends a `retry`
 * hint), so we don't hand-roll reconnection — we only re-emit a `connection`
 * status so the UI can show a live/offline indicator.
 */

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type SSEEventType =
  | "task_created"
  | "task_updated"
  | "member_joined"
  | "deadline_created"
  | "cache_cleared";

export interface SSEEvent {
  type: SSEEventType | string;
  triggered_by?: string;
  timestamp?: string;
  [key: string]: unknown;
}

type Listener = (event: SSEEvent) => void;

interface SSEContextValue {
  connected: boolean;
  /** Subscribe to one event type; returns an unsubscribe function. */
  subscribe: (type: string, listener: Listener) => () => void;
}

const SSEContext = createContext<SSEContextValue | null>(null);

export function SSEProvider({ children }: { children: ReactNode }) {
  const [connected, setConnected] = useState(false);
  // type -> set of listeners. Refs so subscriptions never re-open the stream.
  const listenersRef = useRef<Map<string, Set<Listener>>>(new Map());

  useEffect(() => {
    const source = new EventSource("/api/stream/updates", {
      withCredentials: true,
    });

    const handlePayload = (raw: string) => {
      let payload: SSEEvent;
      try {
        payload = JSON.parse(raw) as SSEEvent;
      } catch {
        return; // ignore heartbeats / malformed frames
      }
      const set = listenersRef.current.get(payload.type);
      if (set) {
        for (const listener of set) {
          try {
            listener(payload);
          } catch (err) {
            console.error("[sse] listener error:", err);
          }
        }
      }
    };

    // Named events from the server (`event: project_update`).
    source.addEventListener("project_update", (e) =>
      handlePayload((e as MessageEvent<string>).data),
    );
    // Fallback for unnamed `message` frames.
    source.onmessage = (e) => handlePayload(e.data);

    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);

    return () => {
      source.close();
      setConnected(false);
    };
  }, []);

  const value = useMemo<SSEContextValue>(
    () => ({
      connected,
      subscribe: (type, listener) => {
        const map = listenersRef.current;
        let set = map.get(type);
        if (!set) {
          set = new Set();
          map.set(type, set);
        }
        set.add(listener);
        return () => {
          set?.delete(listener);
          if (set && set.size === 0) map.delete(type);
        };
      },
    }),
    [connected],
  );

  return <SSEContext.Provider value={value}>{children}</SSEContext.Provider>;
}

export function useSSE(): SSEContextValue {
  const ctx = useContext(SSEContext);
  if (!ctx) {
    throw new Error("useSSE must be used within an <SSEProvider>.");
  }
  return ctx;
}

/**
 * Convenience hook: run `handler` whenever an event of `type` arrives.
 * The handler is kept in a ref so callers don't need to memoize it.
 */
export function useSSEEvent(type: SSEEventType | string, handler: Listener): void {
  const { subscribe } = useSSE();
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    return subscribe(type, (event) => handlerRef.current(event));
  }, [subscribe, type]);
}
