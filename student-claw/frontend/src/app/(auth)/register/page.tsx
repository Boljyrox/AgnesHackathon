"use client";

/** Register page (Phase 1) → POST /api/auth/register → dashboard. */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    display_name: "",
    username: "",
    password: "",
    telegram_username: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function update(key: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          // strip a leading @ if the user typed one
          telegram_username: form.telegram_username.replace(/^@/, "") || undefined,
        }),
      });
      if (res.ok) {
        router.push("/");
        router.refresh();
        return;
      }
      const body = await res.json().catch(() => ({}));
      setError(body.message || "Registration failed.");
    } catch {
      setError("Network error — is the server running?");
    } finally {
      setLoading(false);
    }
  }

  const field =
    "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100";

  return (
    <>
      <h1 className="mb-1 text-xl font-semibold">Create your account</h1>
      <p className="mb-5 text-sm text-slate-500">
        Use the same Telegram username you&apos;ll verify with.
      </p>

      <form onSubmit={onSubmit} className="space-y-4">
        {error && (
          <p
            role="alert"
            className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700"
          >
            {error}
          </p>
        )}

        <div>
          <label htmlFor="display_name" className="mb-1 block text-sm font-medium">
            Display name
          </label>
          <input id="display_name" value={form.display_name} onChange={update("display_name")} required className={field} />
        </div>

        <div>
          <label htmlFor="username" className="mb-1 block text-sm font-medium">
            Username
          </label>
          <input
            id="username"
            value={form.username}
            onChange={update("username")}
            required
            minLength={3}
            pattern="[A-Za-z0-9_]+"
            title="Letters, numbers and underscores only"
            autoComplete="username"
            className={field}
          />
        </div>

        <div>
          <label htmlFor="password" className="mb-1 block text-sm font-medium">
            Password
          </label>
          <input
            id="password"
            type="password"
            value={form.password}
            onChange={update("password")}
            required
            minLength={8}
            autoComplete="new-password"
            className={field}
          />
          <p className="mt-1 text-xs text-slate-400">At least 8 characters.</p>
        </div>

        <div>
          <label htmlFor="telegram_username" className="mb-1 block text-sm font-medium">
            Telegram username
          </label>
          <div className="flex items-center rounded-lg border border-slate-300 focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-100">
            <span className="pl-3 text-sm text-slate-400">@</span>
            <input
              id="telegram_username"
              value={form.telegram_username}
              onChange={update("telegram_username")}
              required
              placeholder="your_telegram_handle"
              className="w-full bg-transparent px-2 py-2 text-sm outline-none"
            />
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Required to link your group via <code>/verify</code>.
          </p>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-brand-500 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-600 disabled:opacity-50"
        >
          {loading ? "Creating account…" : "Create account"}
        </button>
      </form>

      <p className="mt-5 text-center text-sm text-slate-500">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-brand-600 hover:text-brand-700">
          Sign in
        </Link>
      </p>
    </>
  );
}
