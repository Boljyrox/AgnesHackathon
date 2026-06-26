"use client";

import Link from "next/link";

export function SiteNav() {
  return (
    <header className="fixed inset-x-0 top-0 z-50">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
        <Link href="/" data-magnetic className="flex items-center gap-2">
          <img src="/logo.svg" alt="Student Claw" className="h-8 w-8 rounded-lg" />
          <span className="font-semibold tracking-tight text-slate-100">Student Claw</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          <Link
            href="/docs"
            data-magnetic
            className="rounded-lg px-3 py-2 text-slate-300 transition-colors hover:bg-white/5 hover:text-white"
          >
            Docs
          </Link>
          <Link
            href="/login"
            data-magnetic
            className="rounded-lg px-3 py-2 text-slate-300 transition-colors hover:bg-white/5 hover:text-white"
          >
            Sign in
          </Link>
          <Link
            href="/register"
            data-magnetic
            className="rounded-lg bg-brand-500 px-4 py-2 font-medium text-white shadow-glow transition-colors hover:bg-brand-400"
          >
            Get started
          </Link>
        </nav>
      </div>
    </header>
  );
}
