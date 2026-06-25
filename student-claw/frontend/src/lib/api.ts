/**
 * Browser-side API client for the BFF routes.
 *
 * All requests are same-origin and rely on the httpOnly session cookie (sent
 * automatically); we never attach tokens here. Non-2xx responses throw
 * `ApiClientError` so React Query can surface/rollback.
 *
 * NOTE: the per-project task + context endpoints
 * (/api/projects/[id]/tasks, /api/projects/[id]/context) are finalised in
 * Module 6 (backend + BFF). The signatures below define the contract the UI
 * codes against.
 */

import type { Task, TaskStatus } from "@/lib/domain";
import type { ProjectSummary } from "@/lib/types";

export class ApiClientError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
    credentials: "same-origin",
  });
  if (!res.ok) {
    let message = `Request failed (${res.status}).`;
    try {
      const body = (await res.json()) as { message?: string; error?: string };
      message = body.message ?? body.error ?? message;
    } catch {
      /* keep default */
    }
    throw new ApiClientError(res.status, message);
  }
  return (await res.json()) as T;
}

export async function fetchProjects(): Promise<ProjectSummary[]> {
  const { projects } = await request<{ projects: ProjectSummary[] }>("/api/projects");
  return projects;
}

export async function fetchTasks(projectId: string): Promise<Task[]> {
  const { tasks } = await request<{ tasks: Task[] }>(
    `/api/projects/${projectId}/tasks`,
  );
  return tasks;
}

export async function updateTaskStatus(
  projectId: string,
  taskId: string,
  status: TaskStatus,
): Promise<Task> {
  return request<Task>(`/api/projects/${projectId}/tasks/${taskId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export interface AgentAnswer {
  /** Telegram-HTML formatted answer from Agnes. */
  answer_html: string;
}

export async function askAgent(
  projectId: string,
  query: string,
): Promise<AgentAnswer> {
  return request<AgentAnswer>(`/api/projects/${projectId}/context`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}
