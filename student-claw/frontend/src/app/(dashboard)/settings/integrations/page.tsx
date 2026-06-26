"use client";

/**
 * Integrations settings — entry point for the Google Calendar OAuth2 flow (§6.5).
 * The "Connect" button is a plain link to /api/integrations/google/connect, which
 * redirects to Google's consent screen. On return the callback redirects here
 * with ?status=… which we surface as a banner.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

const STATUS_MESSAGES: Record<string, { ok: boolean; text: string }> = {
  success: { ok: true, text: "Google Calendar connected. Confirmed deadlines will sync." },
  denied: { ok: false, text: "You declined the Google permission request." },
  csrf_failed: { ok: false, text: "Security check failed — please try connecting again." },
  session_mismatch: { ok: false, text: "Session changed mid-flow — try again." },
  exchange_failed: { ok: false, text: "Could not complete the Google token exchange." },
  no_refresh_token: { ok: false, text: "Google didn't return a refresh token — revoke access and retry." },
  store_failed: { ok: false, text: "Couldn't save your Google connection. Try again." },
  misconfigured: { ok: false, text: "Google OAuth isn't configured on the server." },
  invalid_response: { ok: false, text: "Invalid response from Google." },
};

export default function IntegrationsPage() {
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    setStatus(new URLSearchParams(window.location.search).get("status"));
  }, []);

  const banner = status ? STATUS_MESSAGES[status] : undefined;

  return (
    <div className="mx-auto max-w-2xl p-4 lg:p-8">
      <h1 className="text-2xl font-semibold">Integrations</h1>
      <p className="mt-1 text-sm text-slate-400">Connect external services to Student Claw.</p>

      {banner && (
        <p
          role="status"
          className={`mt-4 rounded-lg border px-3 py-2 text-sm ${
            banner.ok
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-rose-500/30 bg-rose-500/10 text-rose-300"
          }`}
        >
          {banner.text}
        </p>
      )}

      <section className="mt-6 flex items-center gap-4 rounded-2xl border border-white/10 bg-slate-900/70 p-5">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-slate-800 text-lg">
          📅
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold">Google Calendar</h2>
          <p className="text-sm text-slate-400">
            Push confirmed project deadlines to your primary calendar.
          </p>
        </div>
        <a
          href="/api/integrations/google/connect"
          className="shrink-0 rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-600"
        >
          Connect
        </a>
      </section>

      <p className="mt-6 text-sm text-slate-400">
        <Link href="/settings" className="text-brand-300 hover:text-brand-300">
          ← Back to settings
        </Link>
      </p>
    </div>
  );
}
