/** Client-side domain models for the dashboard UI. */

export type TaskStatus = "pending" | "in_progress" | "done" | "dropped";

/** 1 = High, 2 = Medium, 3 = Low (blueprint §2.3). */
export type Priority = 1 | 2 | 3;

export interface Member {
  id: string;
  displayName: string;
  telegramUsername?: string | null;
  role?: "member" | "lead" | "observer";
}

export interface Task {
  id: string;
  title: string;
  description?: string | null;
  status: TaskStatus;
  priority: Priority;
  assignee?: Member | null;
  deadlineTitle?: string | null;
}

export const TASK_COLUMNS: ReadonlyArray<{
  status: TaskStatus;
  label: string;
  accent: string;
}> = [
  { status: "pending", label: "Pending", accent: "bg-slate-400" },
  { status: "in_progress", label: "In Progress", accent: "bg-brand-500" },
  { status: "done", label: "Done", accent: "bg-emerald-500" },
  { status: "dropped", label: "Dropped", accent: "bg-rose-400" },
];

export const PRIORITY_META: Record<
  Priority,
  { label: string; className: string }
> = {
  1: { label: "High", className: "bg-rose-100 text-rose-700 ring-rose-200" },
  2: { label: "Medium", className: "bg-amber-100 text-amber-700 ring-amber-200" },
  3: { label: "Low", className: "bg-slate-100 text-slate-600 ring-slate-200" },
};
