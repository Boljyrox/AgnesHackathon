/** Per-project RAG Q&A page. */

import { ContextQueryPanel } from "@/components/context/ContextQueryPanel";
import { ProjectTabs } from "@/components/ProjectTabs";

export default function ContextPage({ params }: { params: { projectId: string } }) {
  const { projectId } = params;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-4 border-b border-slate-200 bg-white px-4 py-3 lg:px-6">
        <h1 className="text-lg font-semibold">Project Context</h1>
        <ProjectTabs projectId={projectId} active="context" />
      </div>

      <div className="min-h-0 flex-1 p-4 lg:p-6">
        <div className="mx-auto h-full max-w-2xl">
          <ContextQueryPanel projectId={projectId} />
        </div>
      </div>
    </div>
  );
}
