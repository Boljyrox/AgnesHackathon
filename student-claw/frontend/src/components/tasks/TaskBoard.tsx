"use client";

/**
 * Interactive Kanban board (blueprint §6.4).
 *
 * Multi-container dnd-kit board across the four task statuses. Dropping a card
 * into a new column updates local state optimistically and fires a PATCH to the
 * backend. Real rejections (4xx) roll back; a not-yet-wired endpoint (404/501/
 * network) keeps the optimistic state and shows a non-blocking notice. Live
 * task events from other clients (via SSE) invalidate the query.
 */

import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
  type UniqueIdentifier,
} from "@dnd-kit/core";
import { arrayMove, sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { KanbanColumn } from "@/components/tasks/KanbanColumn";
import { TaskCardContent } from "@/components/tasks/TaskCard";
import { ApiClientError, fetchTasks, updateTaskStatus } from "@/lib/api";
import { TASK_COLUMNS, type Task, type TaskStatus } from "@/lib/domain";
import { useSSEEvent } from "@/providers/SSEProvider";

type Columns = Record<TaskStatus, Task[]>;

const STATUSES = TASK_COLUMNS.map((c) => c.status);

function groupByStatus(tasks: Task[]): Columns {
  const base: Columns = { pending: [], in_progress: [], done: [], dropped: [] };
  for (const task of tasks) base[task.status].push(task);
  return base;
}

function isStatus(id: UniqueIdentifier): id is TaskStatus {
  return STATUSES.includes(id as TaskStatus);
}

export function TaskBoard({
  projectId,
  initialTasks,
}: {
  projectId: string;
  initialTasks: Task[];
}) {
  const queryClient = useQueryClient();

  const { data: tasks } = useQuery({
    queryKey: ["tasks", projectId],
    queryFn: () => fetchTasks(projectId),
    initialData: initialTasks,
    retry: false,
  });

  const [columns, setColumns] = useState<Columns>(() => groupByStatus(initialTasks));
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Snapshot taken at drag start so we can roll back a rejected move.
  const snapshotRef = useRef<Columns | null>(null);
  const isDraggingRef = useRef(false);

  // Re-sync from the query whenever server data changes and we're idle.
  useEffect(() => {
    if (!isDraggingRef.current && tasks) {
      setColumns(groupByStatus(tasks));
    }
  }, [tasks]);

  // Live updates from AI tool executors / other clients.
  useSSEEvent("task_created", () =>
    queryClient.invalidateQueries({ queryKey: ["tasks", projectId] }),
  );
  useSSEEvent("task_updated", () =>
    queryClient.invalidateQueries({ queryKey: ["tasks", projectId] }),
  );

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function findContainer(id: UniqueIdentifier): TaskStatus | null {
    if (isStatus(id)) return id;
    return (
      STATUSES.find((status) => columns[status].some((t) => t.id === id)) ?? null
    );
  }

  function handleDragStart(event: DragStartEvent) {
    isDraggingRef.current = true;
    snapshotRef.current = columns;
    const id = event.active.id;
    const found = STATUSES.flatMap((s) => columns[s]).find((t) => t.id === id);
    setActiveTask(found ?? null);
  }

  function handleDragOver(event: DragOverEvent) {
    const { active, over } = event;
    if (!over) return;
    const activeContainer = findContainer(active.id);
    const overContainer = findContainer(over.id);
    if (!activeContainer || !overContainer || activeContainer === overContainer) {
      return;
    }

    setColumns((prev) => {
      const activeItems = prev[activeContainer];
      const overItems = prev[overContainer];
      const activeIndex = activeItems.findIndex((t) => t.id === active.id);
      if (activeIndex === -1) return prev;

      const insertIndex = isStatus(over.id)
        ? overItems.length
        : Math.max(0, overItems.findIndex((t) => t.id === over.id));

      const moved: Task = { ...activeItems[activeIndex]!, status: overContainer };
      return {
        ...prev,
        [activeContainer]: activeItems.filter((t) => t.id !== active.id),
        [overContainer]: [
          ...overItems.slice(0, insertIndex),
          moved,
          ...overItems.slice(insertIndex),
        ],
      };
    });
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    isDraggingRef.current = false;
    const task = activeTask;
    setActiveTask(null);
    if (!over || !task) return;

    const finalContainer = findContainer(active.id);
    if (!finalContainer) return;

    // Reorder within the same column.
    setColumns((prev) => {
      const items = prev[finalContainer];
      const oldIndex = items.findIndex((t) => t.id === active.id);
      const newIndex = isStatus(over.id)
        ? items.length - 1
        : items.findIndex((t) => t.id === over.id);
      if (oldIndex === -1 || newIndex === -1 || oldIndex === newIndex) return prev;
      return { ...prev, [finalContainer]: arrayMove(items, oldIndex, newIndex) };
    });

    // Status change → persist.
    if (finalContainer !== task.status) {
      void persistStatus(task.id, finalContainer);
    }
  }

  async function persistStatus(taskId: string, status: TaskStatus) {
    const snapshot = snapshotRef.current;
    setNotice(null);
    try {
      await updateTaskStatus(projectId, taskId, status);
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
    } catch (err) {
      const status404 =
        err instanceof ApiClientError && [404, 501].includes(err.status);
      if (status404) {
        // Endpoint not wired yet (Module 6) — keep the optimistic move.
        setNotice("Saved locally — task sync endpoint is not live yet.");
        return;
      }
      // Genuine rejection → roll back.
      if (snapshot) setColumns(snapshot);
      setNotice(
        err instanceof Error ? `Couldn't move task: ${err.message}` : "Couldn't move task.",
      );
    }
  }

  return (
    <div className="flex h-full flex-col">
      {notice && (
        <div
          role="status"
          className="mx-4 mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
        >
          {notice}
        </div>
      )}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        <div className="flex flex-1 gap-4 overflow-x-auto p-4">
          {TASK_COLUMNS.map((col) => (
            <KanbanColumn
              key={col.status}
              status={col.status}
              label={col.label}
              accent={col.accent}
              tasks={columns[col.status]}
            />
          ))}
        </div>

        <DragOverlay>
          {activeTask ? (
            <div className="w-64 rotate-2 rounded-xl border border-brand-200 bg-white p-3 shadow-xl">
              <TaskCardContent task={activeTask} />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
