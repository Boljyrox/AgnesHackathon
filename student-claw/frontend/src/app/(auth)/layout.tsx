/**
 * Auth route-group layout (blueprint §6.1) — a centered card shell with no
 * dashboard sidebar. Used by /login and /register.
 */

import Link from "next/link";
import type { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-screen place-items-center bg-gradient-to-b from-slate-950 to-slate-900 px-4">
      <div className="w-full max-w-sm">
        <Link
          href="/"
          className="mb-6 flex items-center justify-center gap-2 hover:opacity-80 transition-opacity"
        >
          <img
            src="/logo.svg"
            alt="Student Claw Logo"
            className="h-9 w-9 rounded-xl object-contain"
          />
          <span className="text-lg font-semibold">Student Claw</span>
        </Link>

        <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-6 shadow-sm">
          {children}
        </div>
      </div>
    </div>
  );
}
