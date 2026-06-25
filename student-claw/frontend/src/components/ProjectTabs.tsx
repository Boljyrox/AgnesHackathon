/** Shared in-project tab navigation. */

import Link from "next/link";

type Tab = "tasks" | "members" | "context";

const TABS: { key: Tab; label: string; href: (id: string) => string }[] = [
  { key: "tasks", label: "Tasks", href: (id) => `/projects/${id}/tasks` },
  { key: "members", label: "Members", href: (id) => `/projects/${id}/members` },
  { key: "context", label: "Ask Agnes", href: (id) => `/projects/${id}/context` },
];

export function ProjectTabs({ projectId, active }: { projectId: string; active: Tab }) {
  return (
    <nav className="flex gap-1 text-sm">
      {TABS.map((t) =>
        t.key === active ? (
          <span
            key={t.key}
            className="rounded-lg bg-brand-50 px-3 py-1 font-medium text-brand-700"
          >
            {t.label}
          </span>
        ) : (
          <Link
            key={t.key}
            href={t.href(projectId)}
            className="rounded-lg px-3 py-1 text-slate-500 hover:bg-slate-100"
          >
            {t.label}
          </Link>
        ),
      )}
    </nav>
  );
}
