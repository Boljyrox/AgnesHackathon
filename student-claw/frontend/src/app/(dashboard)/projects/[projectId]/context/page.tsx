/** Per-project RAG Q&A page. */

import Link from "next/link";

import { ContextQueryPanel } from "@/components/context/ContextQueryPanel";

export default function ContextPage({ params }: { params: { projectId: string } }) {
  const { projectId } = params;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-4 border-b border-slate-200 bg-white px-4 py-3 lg:px-6">
        <h1 className="text-lg font-semibold">Project Context</h1>
        <nav className="flex gap-1 text-sm">
          <Link
            href={`/projects/${projectId}/tasks`}
            className="rounded-lg px-3 py-1 text-slate-500 hover:bg-slate-100"
          >
            Tasks
          </Link>
          <span className="rounded-lg bg-brand-50 px-3 py-1 font-medium text-brand-700">
            Ask Agnes
          </span>
        </nav>
      </div>

      <div className="min-h-0 flex-1 p-4 lg:p-6">
        <div className="mx-auto h-full max-w-2xl">
          <ContextQueryPanel projectId={projectId} />
        </div>
      </div>
    </div>
  );
}
