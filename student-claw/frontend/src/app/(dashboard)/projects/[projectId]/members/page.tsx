"use client";

/** Per-project team roster — real members (no placeholders). */

import { useQuery } from "@tanstack/react-query";

import { ProjectTabs } from "@/components/ProjectTabs";
import { Avatar } from "@/components/ui/Avatar";
import { fetchMembers } from "@/lib/api";

const ROLE_BADGE: Record<string, string> = {
  lead: "bg-brand-500/20 text-brand-300",
  member: "bg-slate-800 text-slate-300",
  observer: "bg-amber-500/20 text-amber-300",
};

export default function MembersPage({
  params,
}: {
  params: { projectId: string };
}) {
  const { projectId } = params;

  const { data: members, isLoading, isError } = useQuery({
    queryKey: ["members", projectId],
    queryFn: () => fetchMembers(projectId),
  });

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-4 border-b border-white/10 bg-slate-900/70 px-4 py-3 lg:px-6">
        <h1 className="text-lg font-semibold">Team</h1>
        <ProjectTabs projectId={projectId} active="members" />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4 lg:p-6">
        <div className="mx-auto max-w-2xl">
          {isLoading && <p className="text-sm text-slate-400">Loading members…</p>}
          {isError && <p className="text-sm text-rose-400">Couldn&apos;t load members.</p>}

          {members && members.length === 0 && (
            <p className="text-sm text-slate-400">
              No members have verified yet. Share the Project Key so teammates can link in.
            </p>
          )}

          <ul className="space-y-2">
            {members?.map((m) => (
              <li
                key={m.studentId}
                className="flex items-center gap-3 rounded-xl border border-white/10 bg-slate-900/70 p-3"
              >
                <Avatar name={m.displayName} size="lg" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{m.displayName}</p>
                  {m.telegramUsername && (
                    <p className="text-xs text-slate-400">@{m.telegramUsername}</p>
                  )}
                </div>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium capitalize ${
                    ROLE_BADGE[m.role] ?? ROLE_BADGE.member
                  }`}
                >
                  {m.role}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
