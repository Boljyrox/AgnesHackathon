"use client";

/**
 * SUTD_Admin dashboard — Agnes AI request logs + Qdrant vector-store inspector.
 * Dark, diagnostic styling; reads from the admin-gated BFF routes.
 */

import { useQuery } from "@tanstack/react-query";
import { Fragment, useState } from "react";

interface AiLog {
  id: string;
  createdAt: string;
  chatId: number | null;
  kind: string;
  model: string;
  status: string;
  latencyMs: number | null;
  requestSummary: string | null;
  responseSummary: string | null;
  error: string | null;
  totalTokens: number | null;
}
interface Collection {
  name: string;
  chatId: string | null;
  pointCount: number | null;
}
interface Point {
  id: string;
  messageLogId: string | null;
  contentType: string | null;
  sender: string | null;
  source: string | null;
  chunkIndex: number | null;
  textSnippet: string | null;
}

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`Request failed (${r.status})`);
  return r.json() as Promise<T>;
}

const KIND_COLOR: Record<string, string> = {
  chat: "bg-sky-500/15 text-sky-300",
  embedding: "bg-violet-500/15 text-violet-300",
  vision: "bg-amber-500/15 text-amber-300",
};

export function AdminDashboard() {
  const [tab, setTab] = useState<"logs" | "vectors">("logs");

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      <header className="flex items-center gap-4 border-b border-slate-800 px-6 py-4">
        <h1 className="text-lg font-semibold text-slate-100">
          SUTD<span className="text-sky-400">_</span>Admin
        </h1>
        <nav className="flex gap-1 text-sm">
          {(["logs", "vectors"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-lg px-3 py-1 ${
                tab === t ? "bg-sky-500/15 text-sky-300" : "text-slate-400 hover:bg-slate-800"
              }`}
            >
              {t === "logs" ? "Agnes AI Logs" : "Vector Store"}
            </button>
          ))}
        </nav>
        <span className="ml-auto text-xs text-slate-500">diagnostics</span>
      </header>

      <main className="p-6">{tab === "logs" ? <LogsPanel /> : <VectorsPanel />}</main>
    </div>
  );
}

function LogsPanel() {
  const [kind, setKind] = useState<string>("");
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["admin", "ai-logs", kind],
    queryFn: () =>
      getJson<{ logs: AiLog[] }>(`/api/admin/ai-logs?limit=150${kind ? `&kind=${kind}` : ""}`),
  });
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
        >
          <option value="">All kinds</option>
          <option value="chat">chat</option>
          <option value="embedding">embedding</option>
          <option value="vision">vision</option>
        </select>
        <button
          onClick={() => refetch()}
          className="rounded-lg border border-slate-700 px-3 py-1 text-sm hover:bg-slate-800"
        >
          Refresh
        </button>
        <span className="text-xs text-slate-500">{data?.logs.length ?? 0} entries</span>
      </div>

      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {isError && <p className="text-sm text-rose-400">Failed to load logs.</p>}

      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2">Kind</th>
              <th className="px-3 py-2">Model</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Latency</th>
              <th className="px-3 py-2">Request</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {data?.logs.map((log) => (
              <Fragment key={log.id}>
                <tr
                  onClick={() => setOpenId(openId === log.id ? null : log.id)}
                  className="cursor-pointer hover:bg-slate-900"
                >
                  <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-400">
                    {new Date(log.createdAt).toLocaleTimeString()}
                  </td>
                  <td className="px-3 py-2">
                    <span className={`rounded px-1.5 py-0.5 text-xs ${KIND_COLOR[log.kind] ?? ""}`}>
                      {log.kind}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-400">{log.model}</td>
                  <td className="px-3 py-2">
                    <span
                      className={
                        log.status === "success" ? "text-emerald-400" : "text-rose-400"
                      }
                    >
                      {log.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-400">
                    {log.latencyMs != null ? `${log.latencyMs}ms` : "—"}
                  </td>
                  <td className="max-w-xs truncate px-3 py-2 text-slate-300">
                    {log.requestSummary || "—"}
                  </td>
                </tr>
                {openId === log.id && (
                  <tr className="bg-slate-900/60">
                    <td colSpan={6} className="space-y-2 px-3 py-3 text-xs">
                      <Detail label="Response" value={log.responseSummary} />
                      {log.error && <Detail label="Error" value={log.error} error />}
                      <p className="text-slate-500">
                        chat_id: {log.chatId ?? "—"} · tokens: {log.totalTokens ?? "—"}
                      </p>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Detail({ label, value, error }: { label: string; value: string | null; error?: boolean }) {
  return (
    <div>
      <p className="mb-0.5 font-semibold text-slate-400">{label}</p>
      <pre
        className={`overflow-x-auto whitespace-pre-wrap rounded-lg p-2 ${
          error ? "bg-rose-500/10 text-rose-300" : "bg-slate-950 text-slate-300"
        }`}
      >
        {value || "—"}
      </pre>
    </div>
  );
}

function VectorsPanel() {
  const { data: cols, isLoading } = useQuery({
    queryKey: ["admin", "collections"],
    queryFn: () => getJson<{ collections: Collection[] }>("/api/admin/qdrant/collections"),
  });
  const [selected, setSelected] = useState<string | null>(null);

  const { data: points, isFetching } = useQuery({
    queryKey: ["admin", "points", selected],
    queryFn: () =>
      getJson<{ points: Point[]; note?: string }>(
        `/api/admin/qdrant/${selected}/points?limit=100`,
      ),
    enabled: selected !== null,
  });

  return (
    <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
      <aside className="rounded-xl border border-slate-800">
        <p className="border-b border-slate-800 px-3 py-2 text-xs uppercase text-slate-500">
          Collections
        </p>
        {isLoading && <p className="p-3 text-sm text-slate-500">Loading…</p>}
        {cols?.collections.length === 0 && (
          <p className="p-3 text-sm text-slate-500">No collections.</p>
        )}
        <ul className="divide-y divide-slate-800">
          {cols?.collections.map((c) => (
            <li key={c.name}>
              <button
                onClick={() => setSelected(c.chatId)}
                disabled={!c.chatId}
                className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-slate-900 disabled:opacity-50 ${
                  selected === c.chatId ? "bg-sky-500/10 text-sky-300" : "text-slate-300"
                }`}
              >
                <span className="truncate font-mono text-xs">{c.name}</span>
                <span className="ml-2 shrink-0 text-xs text-slate-500">{c.pointCount ?? "?"}</span>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section>
        {selected === null ? (
          <p className="text-sm text-slate-500">Select a collection to inspect its vectors.</p>
        ) : isFetching ? (
          <p className="text-sm text-slate-500">Loading points…</p>
        ) : points?.points.length === 0 ? (
          <p className="text-sm text-slate-500">{points.note || "No vectors stored."}</p>
        ) : (
          <ul className="space-y-2">
            {points?.points.map((p) => (
              <li key={p.id} className="rounded-xl border border-slate-800 bg-slate-900 p-3">
                <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <span className="rounded bg-slate-800 px-1.5 py-0.5">{p.contentType}</span>
                  {p.sender && <span>@{p.sender}</span>}
                  {p.source && <span className="font-mono">{p.source}</span>}
                  <span>chunk #{p.chunkIndex}</span>
                </div>
                <p className="text-sm text-slate-200">{p.textSnippet || "—"}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
