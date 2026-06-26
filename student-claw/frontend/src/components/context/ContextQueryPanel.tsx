"use client";

/**
 * RAG context panel (blueprint §6.4) — chat-style Q&A over a project.
 *
 * Sends questions to /api/projects/[id]/context and renders Agnes's
 * Telegram-HTML answers via a strict DOMPurify allow-list. A "Suggest Summary"
 * button fires a predefined summarisation query.
 */

import { useEffect, useRef, useState } from "react";

import { ApiClientError, askAgent } from "@/lib/api";
import { sanitizeTelegramHtml } from "@/lib/sanitize";

interface ChatMessage {
  id: string;
  role: "user" | "agent";
  /** plain text for user turns; sanitized HTML for agent turns. */
  text?: string;
  html?: string;
  error?: boolean;
}

const SUMMARY_QUERY =
  "Summarise the most recent project updates: key decisions made, deadlines mentioned, and outstanding tasks. Keep it concise.";

let counter = 0;
const nextId = () => `m${++counter}`;

export function ContextQueryPanel({ projectId }: { projectId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, pending]);

  async function send(query: string) {
    const trimmed = query.trim();
    if (!trimmed || pending) return;

    setMessages((m) => [...m, { id: nextId(), role: "user", text: trimmed }]);
    setInput("");
    setPending(true);

    try {
      const { answer_html } = await askAgent(projectId, trimmed);
      setMessages((m) => [
        ...m,
        { id: nextId(), role: "agent", html: sanitizeTelegramHtml(answer_html) },
      ]);
    } catch (err) {
      const message =
        err instanceof ApiClientError && [404, 501].includes(err.status)
          ? "The project Q&A endpoint isn't live yet (lands in Module 6)."
          : err instanceof Error
            ? err.message
            : "Something went wrong.";
      setMessages((m) => [
        ...m,
        { id: nextId(), role: "agent", text: message, error: true },
      ]);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/10 bg-slate-900/70">
      <header className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-brand-500 text-xs font-bold text-white">
          AI
        </span>
        <div>
          <h2 className="text-sm font-semibold">Ask Agnes</h2>
          <p className="text-xs text-slate-400">Answers grounded in this project&apos;s history</p>
        </div>
        <button
          type="button"
          onClick={() => send(SUMMARY_QUERY)}
          disabled={pending}
          className="ml-auto rounded-lg border border-brand-500/30 bg-brand-500/10 px-3 py-1.5 text-xs font-medium text-brand-300 transition-colors hover:bg-brand-500/20 disabled:opacity-50"
        >
          Suggest Summary
        </button>
      </header>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
        {messages.length === 0 && !pending && (
          <div className="grid h-full place-items-center text-center text-sm text-slate-400">
            <p>
              Ask anything about this project — decisions, deadlines, who did what.
              <br />
              Try the <span className="font-medium text-brand-300">Suggest Summary</span> button.
            </p>
          </div>
        )}

        {messages.map((m) =>
          m.role === "user" ? (
            <div key={m.id} className="flex justify-end">
              <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-brand-500 px-3 py-2 text-sm text-white">
                {m.text}
              </div>
            </div>
          ) : (
            <div key={m.id} className="flex justify-start">
              <div
                className={`max-w-[85%] rounded-2xl rounded-bl-sm px-3 py-2 text-sm ${
                  m.error
                    ? "bg-rose-500/10 text-rose-300"
                    : "bg-slate-800 text-slate-100"
                }`}
              >
                {m.html !== undefined ? (
                  <div
                    className="agnes-html whitespace-pre-wrap break-words"
                    // Sanitized to the Telegram tag subset before rendering.
                    dangerouslySetInnerHTML={{ __html: m.html }}
                  />
                ) : (
                  <span>{m.text}</span>
                )}
              </div>
            </div>
          ),
        )}

        {pending && (
          <div className="flex justify-start">
            <div className="flex items-center gap-1 rounded-2xl rounded-bl-sm bg-slate-800 px-3 py-2.5">
              <Dot delay="0ms" />
              <Dot delay="120ms" />
              <Dot delay="240ms" />
            </div>
          </div>
        )}
      </div>

      <form
        className="flex items-center gap-2 border-t border-white/10 p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
        }}
      >
        <label htmlFor="agnes-input" className="sr-only">
          Ask about this project
        </label>
        <input
          id="agnes-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about this project…"
          autoComplete="off"
          className="flex-1 rounded-lg border border-white/10 px-3 py-2 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-500/30"
        />
        <button
          type="submit"
          disabled={pending || !input.trim()}
          className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-600 disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-500"
      style={{ animationDelay: delay }}
      aria-hidden="true"
    />
  );
}
