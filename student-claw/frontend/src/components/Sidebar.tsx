"use client";

/**
 * Dashboard sidebar (blueprint §6.4): project navigation + user/avatar menu.
 * Responsive — a fixed rail on lg+, a slide-in drawer on mobile driven by the
 * Zustand UI store. Includes a skip-friendly nav landmark and focus states.
 */

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Avatar } from "@/components/ui/Avatar";
import { fetchProjects } from "@/lib/api";
import { useUIStore } from "@/store/ui";

function statusDot(status: string): string {
  switch (status) {
    case "active":
      return "bg-emerald-500";
    case "clearing":
      return "bg-amber-500";
    default:
      return "bg-slate-300";
  }
}

export function Sidebar({ username = "You" }: { username?: string }) {
  const pathname = usePathname();
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const setSidebar = useUIStore((s) => s.setSidebar);
  const [menuOpen, setMenuOpen] = useState(false);

  const { data: projects, isLoading, isError } = useQuery({
    queryKey: ["projects"],
    queryFn: fetchProjects,
  });

  return (
    <>
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden"
          aria-hidden="true"
          onClick={() => setSidebar(false)}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200 bg-white transition-transform duration-200 lg:static lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Primary"
      >
        {/* Brand */}
        <div className="flex h-14 items-center gap-2 border-b border-slate-200 px-4">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-brand-500 text-sm font-bold text-white">
            SC
          </span>
          <span className="font-semibold">Student Claw</span>
        </div>

        {/* Project nav */}
        <nav className="flex-1 overflow-y-auto p-3" aria-label="Projects">
          <p className="px-2 pb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
            Projects
          </p>

          {isLoading && (
            <ul className="space-y-1" aria-hidden="true">
              {Array.from({ length: 3 }).map((_, i) => (
                <li key={i} className="h-9 animate-pulse rounded-lg bg-slate-100" />
              ))}
            </ul>
          )}

          {isError && (
            <p className="px-2 text-sm text-rose-600">Couldn&apos;t load projects.</p>
          )}

          {projects && projects.length === 0 && (
            <p className="px-2 text-sm text-slate-500">
              No projects yet.{" "}
              <Link href="/projects/link" className="text-brand-600 underline">
                Link one
              </Link>
              .
            </p>
          )}

          <ul className="space-y-1">
            {projects?.map((p) => {
              const href = `/projects/${p.id}/tasks`;
              const active = pathname?.startsWith(`/projects/${p.id}`);
              return (
                <li key={p.id}>
                  <Link
                    href={href}
                    onClick={() => setSidebar(false)}
                    aria-current={active ? "page" : undefined}
                    className={`flex items-center gap-2 rounded-lg px-2 py-2 text-sm transition-colors ${
                      active
                        ? "bg-brand-50 font-medium text-brand-700"
                        : "text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    <span
                      className={`h-2 w-2 shrink-0 rounded-full ${statusDot(p.status)}`}
                      aria-hidden="true"
                    />
                    <span className="truncate">{p.name}</span>
                    {p.module_code && (
                      <span className="ml-auto shrink-0 text-xs text-slate-400">
                        {p.module_code}
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* User / settings menu */}
        <div className="relative border-t border-slate-200 p-3">
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left hover:bg-slate-100"
          >
            <Avatar name={username} size="md" />
            <span className="truncate text-sm font-medium">{username}</span>
            <svg
              className="ml-auto h-4 w-4 text-slate-400"
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path d="M5.5 8l4.5 4 4.5-4" stroke="currentColor" strokeWidth="1.5" fill="none" />
            </svg>
          </button>

          {menuOpen && (
            <div
              role="menu"
              className="absolute bottom-16 left-3 right-3 z-10 animate-fade-in rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
            >
              <Link
                href="/settings"
                role="menuitem"
                className="block px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
                onClick={() => setMenuOpen(false)}
              >
                Account settings
              </Link>
              <Link
                href="/settings/integrations"
                role="menuitem"
                className="block px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
                onClick={() => setMenuOpen(false)}
              >
                Integrations
              </Link>
              <form action="/api/auth/logout" method="post">
                <button
                  type="submit"
                  role="menuitem"
                  className="block w-full px-3 py-2 text-left text-sm text-rose-600 hover:bg-rose-50"
                >
                  Sign out
                </button>
              </form>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
