"use client";

/** A single draggable task card (blueprint §6.4). */

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { Avatar } from "@/components/ui/Avatar";
import { PRIORITY_META, type Task } from "@/lib/domain";

export function PriorityBadge({ priority }: { priority: Task["priority"] }) {
  const meta = PRIORITY_META[priority];
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ring-inset ${meta.className}`}
    >
      {meta.label}
    </span>
  );
}

export function TaskCardContent({ task }: { task: Task }) {
  return (
    <div className="space-y-2">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium leading-snug text-slate-800">{task.title}</p>
        <PriorityBadge priority={task.priority} />
      </div>

      {task.deadlineTitle && (
        <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600">
          <svg className="h-3 w-3" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
            <path d="M8 4v4l3 2-.75 1.2L7 9V4z M8 1a7 7 0 100 14A7 7 0 008 1z" />
          </svg>
          {task.deadlineTitle}
        </span>
      )}

      <div className="flex items-center gap-2 pt-1">
        {task.assignee ? (
          <>
            <Avatar name={task.assignee.displayName} size="sm" />
            <span className="text-xs text-slate-500">{task.assignee.displayName}</span>
          </>
        ) : (
          <span className="text-xs italic text-slate-400">Unassigned</span>
        )}
      </div>
    </div>
  );
}

export function TaskCard({ task }: { task: Task }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: task.id, data: { status: task.status } });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <li
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={`cursor-grab touch-none rounded-xl border border-slate-200 bg-white p-3 shadow-sm outline-none transition-shadow focus-visible:ring-2 focus-visible:ring-brand-500 active:cursor-grabbing ${
        isDragging ? "opacity-40" : "hover:shadow-md"
      }`}
      aria-roledescription="Draggable task"
    >
      <TaskCardContent task={task} />
    </li>
  );
}
