"use client";

/** Mobile menu toggle + real-time connection indicator. */

import { useSSE } from "@/providers/SSEProvider";
import { useUIStore } from "@/store/ui";

export function Topbar() {
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const { connected } = useSSE();

  return (
    <header className="flex h-14 items-center gap-3 border-b border-slate-200 bg-white px-4 lg:px-6">
      <button
        type="button"
        onClick={toggleSidebar}
        className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
        aria-label="Toggle navigation"
      >
        <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" stroke="currentColor">
          <path d="M3 5h14M3 10h14M3 15h14" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      </button>

      <div className="ml-auto flex items-center gap-2 text-xs">
        <span
          className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-500" : "bg-slate-300"}`}
          aria-hidden="true"
        />
        <span className="text-slate-500" aria-live="polite">
          {connected ? "Live" : "Reconnecting…"}
        </span>
      </div>
    </header>
  );
}
