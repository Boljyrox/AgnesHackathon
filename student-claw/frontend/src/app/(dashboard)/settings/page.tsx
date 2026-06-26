/** Account settings (blueprint §6.1). */

import Link from "next/link";

import { getSession } from "@/lib/auth";

export default async function SettingsPage() {
  const auth = await getSession();

  return (
    <div className="mx-auto max-w-2xl p-4 lg:p-8">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <section className="mt-6 rounded-2xl border border-white/10 bg-slate-900/70 p-5">
        <h2 className="text-sm font-semibold text-slate-200">Account</h2>
        <dl className="mt-3 grid grid-cols-[120px_1fr] gap-y-2 text-sm">
          <dt className="text-slate-400">Username</dt>
          <dd className="font-medium">{auth?.session.username ?? "—"}</dd>
          <dt className="text-slate-400">Telegram</dt>
          <dd>
            {auth?.session.telegram_verified ? (
              <span className="text-emerald-400">Verified</span>
            ) : (
              <span className="text-amber-400">Not linked yet</span>
            )}
          </dd>
        </dl>
      </section>

      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <Link
          href="/settings/integrations"
          className="rounded-2xl border border-white/10 bg-slate-900/70 p-5 transition-colors hover:border-brand-500/30 hover:bg-brand-500/10"
        >
          <h3 className="text-sm font-semibold">Integrations</h3>
          <p className="text-sm text-slate-400">Connect Google Calendar.</p>
        </Link>
        <Link
          href="/projects/link"
          className="rounded-2xl border border-white/10 bg-slate-900/70 p-5 transition-colors hover:border-brand-500/30 hover:bg-brand-500/10"
        >
          <h3 className="text-sm font-semibold">Link a project</h3>
          <p className="text-sm text-slate-400">Connect a Telegram group.</p>
        </Link>
      </div>
    </div>
  );
}
