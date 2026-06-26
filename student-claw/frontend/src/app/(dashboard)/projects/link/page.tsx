"use client";

/**
 * Link a project (blueprint §4.1 Phase 3).
 * Enter the Project Key from the bot's welcome message → receive a short-lived
 * token + the exact /verify command to send in the Telegram group.
 */

import Link from "next/link";
import { useState } from "react";

interface LinkResult {
  token: string;
  expires_at: string;
  instructions: string;
}

export default function LinkProjectPage() {
  const [projectKey, setProjectKey] = useState("");
  const [result, setResult] = useState<LinkResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/projects/link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_key: projectKey.trim() }),
      });
      const body = await res.json().catch(() => ({}));
      if (res.ok) {
        setResult(body as LinkResult);
      } else {
        setError(body.message || "Couldn't link that project.");
      }
    } catch {
      setError("Network error — is the server running?");
    } finally {
      setLoading(false);
    }
  }

  const verifyCommand = result ? `/verify ${result.token}` : "";

  async function copy() {
    await navigator.clipboard.writeText(verifyCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="mx-auto max-w-xl p-4 lg:p-8">
      <h1 className="text-2xl font-semibold">Link a project</h1>
      <p className="mt-1 text-sm text-slate-400">
        Add <span className="font-medium">@StudentClawBot</span> to your Telegram group,
        then paste the Project Key it gives you below.
      </p>

      <form
        onSubmit={onSubmit}
        className="mt-6 rounded-2xl border border-white/10 bg-slate-900/70 p-5"
      >
        <label htmlFor="key" className="mb-1 block text-sm font-medium">
          Project Key
        </label>
        <div className="flex gap-2">
          <input
            id="key"
            value={projectKey}
            onChange={(e) => setProjectKey(e.target.value)}
            required
            placeholder="SC-4f8a2b9e1c3d7f0a"
            className="flex-1 rounded-lg border border-white/10 px-3 py-2 font-mono text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-500/30"
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-600 disabled:opacity-50"
          >
            {loading ? "Linking…" : "Link"}
          </button>
        </div>

        {error && (
          <p
            role="alert"
            className="mt-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-300"
          >
            {error}
          </p>
        )}
      </form>

      {result && (
        <div className="mt-6 animate-fade-in rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-5">
          <h2 className="text-sm font-semibold text-emerald-300">
            Almost there — verify in Telegram
          </h2>
          <p className="mt-1 text-sm text-emerald-300">
            Send this command in your group chat within 15 minutes:
          </p>

          <div className="mt-3 flex items-center gap-2">
            <code className="flex-1 overflow-x-auto rounded-lg bg-slate-900/70 px-3 py-2 font-mono text-xs text-slate-100 ring-1 ring-emerald-500/30">
              {verifyCommand}
            </code>
            <button
              type="button"
              onClick={copy}
              className="shrink-0 rounded-lg border border-emerald-500/40 bg-slate-900/70 px-3 py-2 text-xs font-medium text-emerald-300 hover:bg-emerald-500/20"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>

          <p className="mt-3 text-xs text-emerald-300">
            Once verified, your project appears in the sidebar automatically.
          </p>
        </div>
      )}

      <p className="mt-6 text-sm text-slate-400">
        <Link href="/" className="text-brand-300 hover:text-brand-300">
          ← Back to dashboard
        </Link>
      </p>
    </div>
  );
}
