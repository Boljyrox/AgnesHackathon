/** Dashboard overview (blueprint §6.1). */

import { Avatar } from "@/components/ui/Avatar";
import { PLACEHOLDER_MEMBERS } from "@/lib/placeholder";

export default function OverviewPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 lg:p-8">
      <header>
        <h1 className="text-2xl font-semibold">Welcome back 👋</h1>
        <p className="text-sm text-slate-500">
          Pick a project from the sidebar to view its board, deadlines and context.
        </p>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Your team</h2>
        <ul className="flex flex-wrap gap-3">
          {PLACEHOLDER_MEMBERS.map((m) => (
            <li
              key={m.id}
              className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2"
            >
              <Avatar name={m.displayName} size="md" />
              <div className="leading-tight">
                <p className="text-sm font-medium">{m.displayName}</p>
                <p className="text-xs capitalize text-slate-400">{m.role}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
