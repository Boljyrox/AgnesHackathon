"use client";

/** A droppable Kanban column hosting a sortable list of task cards. */

import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";

import { TaskCard } from "@/components/tasks/TaskCard";
import type { MemberDto } from "@/lib/api";
import type { Task, TaskStatus } from "@/lib/domain";

export function KanbanColumn({
  status,
  label,
  accent,
  tasks,
  projectId,
  members,
}: {
  status: TaskStatus;
  label: string;
  accent: string;
  tasks: Task[];
  projectId: string;
  members: MemberDto[];
}) {
  // The column itself is a droppable so empty columns still accept drops.
  const { setNodeRef, isOver } = useDroppable({ id: status });

  return (
    <section
      className="flex w-72 shrink-0 flex-col rounded-2xl bg-slate-100/70"
      aria-label={`${label} column`}
    >
      <header className="flex items-center gap-2 px-3 py-3">
        <span className={`h-2.5 w-2.5 rounded-full ${accent}`} aria-hidden="true" />
        <h2 className="text-sm font-semibold text-slate-700">{label}</h2>
        <span className="ml-auto rounded-full bg-white px-2 py-0.5 text-xs font-medium text-slate-500">
          {tasks.length}
        </span>
      </header>

      <SortableContext
        items={tasks.map((t) => t.id)}
        strategy={verticalListSortingStrategy}
      >
        <ul
          ref={setNodeRef}
          className={`flex min-h-[120px] flex-1 flex-col gap-2 overflow-y-auto rounded-xl px-2 pb-3 transition-colors ${
            isOver ? "bg-brand-50/60 ring-2 ring-inset ring-brand-200" : ""
          }`}
        >
          {tasks.map((task) => (
            <TaskCard key={task.id} task={task} projectId={projectId} members={members} />
          ))}

          {tasks.length === 0 && (
            <li className="grid flex-1 place-items-center rounded-xl border-2 border-dashed border-slate-200 py-6 text-xs text-slate-400">
              Drop tasks here
            </li>
          )}
        </ul>
      </SortableContext>
    </section>
  );
}
