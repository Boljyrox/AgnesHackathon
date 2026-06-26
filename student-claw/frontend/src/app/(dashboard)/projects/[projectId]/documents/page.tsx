"use client";

/** Project Documents tab — all files shared in the Telegram chat. */

import { useQuery } from "@tanstack/react-query";

import { ProjectTabs } from "@/components/ProjectTabs";
import { documentDownloadUrl, fetchDocuments, type ProjectDocument } from "@/lib/api";

function fileIcon(doc: ProjectDocument): string {
  if (doc.contentType === "image") return "🖼️";
  if ((doc.mimeType ?? "").includes("pdf") || doc.filename.endsWith(".pdf")) return "📄";
  if (doc.filename.endsWith(".pptx")) return "📊";
  return "📎";
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function DocumentsPage({
  params,
}: {
  params: { projectId: string };
}) {
  const { projectId } = params;
  const { data: docs, isLoading, isError } = useQuery({
    queryKey: ["documents", projectId],
    queryFn: () => fetchDocuments(projectId),
  });

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-4 border-b border-white/10 bg-slate-900/70 px-4 py-3 lg:px-6">
        <h1 className="text-lg font-semibold">Documents</h1>
        <ProjectTabs projectId={projectId} active="documents" />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4 lg:p-6">
        <div className="mx-auto max-w-3xl">
          {isLoading && <p className="text-sm text-slate-400">Loading files…</p>}
          {isError && <p className="text-sm text-rose-400">Couldn&apos;t load documents.</p>}

          {docs && docs.length === 0 && (
            <div className="rounded-2xl border border-dashed border-white/10 bg-slate-900/70 p-8 text-center text-sm text-slate-400">
              No files shared yet. Share a PDF, image or slide deck in the Telegram
              group, then run <code>/sync</code> to index them here.
            </div>
          )}

          <ul className="space-y-2">
            {docs?.map((doc) => (
              <li
                key={doc.id}
                className="flex items-center gap-3 rounded-xl border border-white/10 bg-slate-900/70 p-3"
              >
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-slate-800 text-xl">
                  {fileIcon(doc)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-100">{doc.filename}</p>
                  <p className="text-xs text-slate-400">
                    {doc.sender ? `@${doc.sender} · ` : ""}
                    {formatDate(doc.receivedAt)}
                  </p>
                </div>

                {/* Indexed status — green when searchable by Agnes */}
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                    doc.isVectorized
                      ? "bg-emerald-500/20 text-emerald-300"
                      : doc.hasText
                        ? "bg-amber-500/20 text-amber-300"
                        : "bg-slate-800 text-slate-400"
                  }`}
                  title={
                    doc.isVectorized
                      ? "Indexed — Agnes can answer questions about this"
                      : "Not indexed yet — run /sync in the group"
                  }
                >
                  {doc.isVectorized ? "Indexed" : doc.hasText ? "Read" : "Pending"}
                </span>

                <a
                  href={documentDownloadUrl(projectId, doc.id)}
                  target="_blank"
                  rel="noreferrer"
                  className="shrink-0 rounded-lg border border-white/10 px-3 py-1 text-xs font-medium text-brand-300 hover:bg-brand-500/10"
                >
                  Open
                </a>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
