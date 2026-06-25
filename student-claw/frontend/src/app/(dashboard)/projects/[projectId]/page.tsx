"use client";

/**
 * Project overview — the Project Goals card front and centre (Requirement 3),
 * with inline editing, plus quick project stats.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ProjectTabs } from "@/components/ProjectTabs";
import { fetchProject, updateProjectGoals } from "@/lib/api";

export default function ProjectOverviewPage({
  params,
}: {
  params: { projectId: string };
}) {
  const { projectId } = params;
  const qc = useQueryClient();

  const { data: project, isLoading, isError } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => fetchProject(projectId),
  });

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  useEffect(() => {
    if (project) setDraft(project.goals ?? "");
  }, [project]);

  const save = useMutation({
    mutationFn: () => updateProjectGoals(projectId, draft),
    onSuccess: () => {
      setEditing(false);
      qc.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-4 border-b border-slate-200 bg-white px-4 py-3 lg:px-6">
        <h1 className="text-lg font-semibold">{project?.name ?? "Project"}</h1>
        <ProjectTabs projectId={projectId} active="overview" />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4 lg:p-8">
        <div className="mx-auto max-w-3xl space-y-6">
          {isLoading && <p className="text-sm text-slate-400">Loading…</p>}
          {isError && <p className="text-sm text-rose-600">Couldn&apos;t load this project.</p>}

          {project && (
            <>
              {/* Project Goals — front and centre */}
              <section className="overflow-hidden rounded-2xl border border-brand-200 bg-gradient-to-br from-brand-50 to-white shadow-sm">
                <div className="flex items-center justify-between border-b border-brand-100 px-5 py-3">
                  <h2 className="flex items-center gap-2 text-sm font-semibold text-brand-800">
                    <span>🎯</span> Project Goals
                  </h2>
                  {!editing && (
                    <button
                      onClick={() => setEditing(true)}
                      className="rounded-lg border border-brand-200 bg-white px-3 py-1 text-xs font-medium text-brand-700 hover:bg-brand-50"
                    >
                      {project.goals ? "Edit" : "Add goals"}
                    </button>
                  )}
                </div>

                <div className="px-5 py-4">
                  {editing ? (
                    <div className="space-y-3">
                      <textarea
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        rows={6}
                        autoFocus
                        placeholder="What is this project trying to achieve? List the key objectives…"
                        className="w-full resize-y rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => save.mutate()}
                          disabled={save.isPending}
                          className="rounded-lg bg-brand-500 px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
                        >
                          {save.isPending ? "Saving…" : "Save goals"}
                        </button>
                        <button
                          onClick={() => {
                            setEditing(false);
                            setDraft(project.goals ?? "");
                          }}
                          className="rounded-lg px-3 py-1.5 text-sm text-slate-500 hover:bg-slate-100"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : project.goals ? (
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                      {project.goals}
                    </p>
                  ) : (
                    <p className="text-sm italic text-slate-400">
                      No goals set yet. Add them here, or ask Agnes in the group with{" "}
                      <code>/project_goals</code>.
                    </p>
                  )}
                </div>
              </section>

              {/* Quick stats */}
              <section className="grid gap-3 sm:grid-cols-3">
                <Stat label="Status" value={project.status} />
                <Stat label="Your role" value={project.role} />
                <Stat label="Members" value={String(project.memberCount)} />
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-lg font-semibold capitalize text-slate-800">{value}</p>
    </div>
  );
}
