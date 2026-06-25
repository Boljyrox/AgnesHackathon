/** Per-project Kanban page. */

import { ProjectTabs } from "@/components/ProjectTabs";
import { TaskBoard } from "@/components/tasks/TaskBoard";

export default function TasksPage({ params }: { params: { projectId: string } }) {
  const { projectId } = params;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-4 border-b border-slate-200 bg-white px-4 py-3 lg:px-6">
        <h1 className="text-lg font-semibold">Task Board</h1>
        <ProjectTabs projectId={projectId} active="tasks" />
      </div>

      <div className="min-h-0 flex-1">
        <TaskBoard projectId={projectId} />
      </div>
    </div>
  );
}
