"use client";

/**
 * Home dashboard — personal task manager.
 * Shows the student's projects, upcoming deadlines across all projects, and a
 * personal to-do list (open tasks assigned to them). All real data from
 * /api/me/overview; no placeholders.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";

import {
  fetchOverview,
  updateTaskStatus,
  type OverviewDeadline,
  type OverviewTodo,
} from "@/lib/api";
import { PRIORITY_META, type Priority } from "@/lib/domain";
import { useSSEEvent } from "@/providers/SSEProvider";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function dueRelative(iso: string): { label: string; tone: string } {
  const ms = new Date(iso).getTime() - Date.now();
  const days = Math.round(ms / 86_400_000);
  if (ms < 0) return { label: "overdue", tone: "text-rose-600" };
  if (days === 0) return { label: "today", tone: "text-amber-600" };
  if (days === 1) return { label: "tomorrow", tone: "text-amber-600" };
  return { label: `in ${days} days`, tone: "text-slate-400" };
}

export default function OverviewPage() {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["overview"],
    queryFn: fetchOverview,
  });

  // Live refresh when tasks/deadlines change anywhere.
  useSSEEvent("task_created", () => qc.invalidateQueries({ queryKey: ["overview"] }));
  useSSEEvent("task_updated", () => qc.invalidateQueries({ queryKey: ["overview"] }));
  useSSEEvent("member_joined", () => qc.invalidateQueries({ queryKey: ["overview"] }));

  const completeTodo = useMutation({
    mutationFn: (t: OverviewTodo) => updateTaskStatus(t.projectId, t.id, "done"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["overview"] }),
  });

  if (isLoading) {
    return <div className="p-8 text-sm text-slate-400">Loading your dashboard…</div>;
  }
  if (isError || !data) {
    return <div className="p-8 text-sm text-rose-600">Couldn&apos;t load your dashboard.</div>;
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 p-4 lg:p-8">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Hi, {data.displayName} 👋</h1>
          <p className="text-sm text-slate-500">
            {data.projects.length} project{data.projects.length === 1 ? "" : "s"} ·{" "}
            {data.todos.length} open task{data.todos.length === 1 ? "" : "s"}
          </p>
        </div>
        <Link
          href="/projects/link"
          className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-600"
        >
          + Link a project
        </Link>
      </header>

      {/* Projects */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Your projects
        </h2>
        {data.projects.length === 0 ? (
          <EmptyCard>
            You&apos;re not in any projects yet.{" "}
            <Link href="/projects/link" className="font-medium text-brand-600">
              Link a Telegram group
            </Link>{" "}
            to get started.
          </EmptyCard>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.projects.map((p) => (
              <Link
                key={p.id}
                href={`/projects/${p.id}`}
                className="rounded-2xl border border-slate-200 bg-white p-4 transition-colors hover:border-brand-200 hover:bg-brand-50"
              >
                <div className="flex items-center justify-between">
                  <h3 className="truncate font-medium">{p.name}</h3>
                  <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs capitalize text-slate-500">
                    {p.role}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-400">
                  {p.moduleCode ? `${p.moduleCode} · ` : ""}
                  {p.memberCount} member{p.memberCount === 1 ? "" : "s"}
                </p>
              </Link>
            ))}
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* To-do list */}
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            My to-do list
          </h2>
          <div className="rounded-2xl border border-slate-200 bg-white">
            {data.todos.length === 0 ? (
              <p className="p-5 text-sm text-slate-400">Nothing on your plate. 🎉</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {data.todos.map((t) => (
                  <TodoRow
                    key={t.id}
                    todo={t}
                    onComplete={() => completeTodo.mutate(t)}
                    busy={completeTodo.isPending}
                  />
                ))}
              </ul>
            )}
          </div>
        </section>

        {/* Deadlines */}
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Upcoming deadlines
          </h2>
          <div className="rounded-2xl border border-slate-200 bg-white">
            {data.deadlines.length === 0 ? (
              <p className="p-5 text-sm text-slate-400">No deadlines yet.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {data.deadlines.map((d) => (
                  <DeadlineRow key={d.id} deadline={d} />
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function TodoRow({
  todo,
  onComplete,
  busy,
}: {
  todo: OverviewTodo;
  onComplete: () => void;
  busy: boolean;
}) {
  const meta = PRIORITY_META[todo.priority as Priority] ?? PRIORITY_META[2];
  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <button
        type="button"
        onClick={onComplete}
        disabled={busy}
        aria-label="Mark done"
        className="grid h-5 w-5 shrink-0 place-items-center rounded-full border border-slate-300 text-transparent transition-colors hover:border-emerald-500 hover:bg-emerald-500 hover:text-white disabled:opacity-50"
      >
        ✓
      </button>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-800">{todo.title}</p>
        <p className="text-xs text-slate-400">{todo.projectName}</p>
      </div>
      <span
        className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ring-1 ring-inset ${meta.className}`}
      >
        {meta.label}
      </span>
    </li>
  );
}

function DeadlineRow({ deadline }: { deadline: OverviewDeadline }) {
  const rel = dueRelative(deadline.dueDate);
  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-slate-100 text-base">
        📅
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-800">{deadline.title}</p>
        <p className="text-xs text-slate-400">
          {deadline.projectName} · {formatDate(deadline.dueDate)}
        </p>
      </div>
      <div className="shrink-0 text-right">
        <p className={`text-xs font-medium ${rel.tone}`}>{rel.label}</p>
        {!deadline.isConfirmed && (
          <p className="text-[10px] text-amber-500">unconfirmed</p>
        )}
      </div>
    </li>
  );
}

function EmptyCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-6 text-sm text-slate-500">
      {children}
    </div>
  );
}
