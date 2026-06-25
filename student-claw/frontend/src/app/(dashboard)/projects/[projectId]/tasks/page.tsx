/**
 * Per-project Kanban page (blueprint §6.1).
 * Seeds the board with placeholder tasks until the task endpoints land (M6).
 */

import Link from "next/link";

import { TaskBoard } from "@/components/tasks/TaskBoard";
import { PLACEHOLDER_TASKS } from "@/lib/placeholder";

export default function TasksPage({ params }: { params: { projectId: string } }) {
  const { projectId } = params;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-4 border-b border-slate-200 bg-white px-4 py-3 lg:px-6">
        <h1 className="text-lg font-semibold">Task Board</h1>
        <nav className="flex gap-1 text-sm">
          <span className="rounded-lg bg-brand-50 px-3 py-1 font-medium text-brand-700">
            Tasks
          </span>
          <Link
            href={`/projects/${projectId}/context`}
            className="rounded-lg px-3 py-1 text-slate-500 hover:bg-slate-100"
          >
            Ask Agnes
          </Link>
        </nav>
      </div>

      <div className="min-h-0 flex-1">
        <TaskBoard projectId={projectId} initialTasks={PLACEHOLDER_TASKS} />
      </div>
    </div>
  );
}
