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

export interface OverviewProject {
  id: string;
  name: string;
  moduleCode: string | null;
  status: string;
  role: string;
  memberCount: number;
}
export interface OverviewDeadline {
  id: string;
  title: string;
  dueDate: string;
  projectId: string;
  projectName: string;
  isConfirmed: boolean;
}
export interface OverviewTodo {
  id: string;
  title: string;
  status: TaskStatus;
  priority: number;
  projectId: string;
  projectName: string;
}
export interface Overview {
  displayName: string;
  username: string;
  telegramVerified: boolean;
  projects: OverviewProject[];
  deadlines: OverviewDeadline[];
  todos: OverviewTodo[];
}

export async function fetchOverview(): Promise<Overview> {
  return request<Overview>("/api/me/overview");
}

export interface MemberDto {
  studentId: string;
  displayName: string;
  telegramUsername: string | null;
  role: string;
}

export async function fetchMembers(projectId: string): Promise<MemberDto[]> {
  return request<MemberDto[]>(`/api/projects/${projectId}/members`);
}

export interface ProjectDocument {
  id: string;
  filename: string;
  contentType: "image" | "document";
  mimeType: string | null;
  sender: string | null;
  receivedAt: string;
  isVectorized: boolean;
  hasText: boolean;
}

export async function fetchDocuments(projectId: string): Promise<ProjectDocument[]> {
  const { documents } = await request<{ documents: ProjectDocument[] }>(
    `/api/projects/${projectId}/documents`,
  );
  return documents;
}

export function documentDownloadUrl(projectId: string, docId: string): string {
  return `/api/projects/${projectId}/documents/${docId}/download`;
}

export async function fetchTasks(projectId: string): Promise<Task[]> {
  const { tasks } = await request<{ tasks: Task[] }>(
    `/api/projects/${projectId}/tasks`,
  );
  return tasks;
}

export interface CreateTaskInput {
  title: string;
  description?: string;
  priority?: number;
  assignee_telegram_username?: string;
}

export async function createTask(
  projectId: string,
  input: CreateTaskInput,
): Promise<Task> {
  return request<Task>(`/api/projects/${projectId}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
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

export async function updateTaskAssignee(
  projectId: string,
  taskId: string,
  telegramUsername: string | null,
): Promise<Task> {
  return request<Task>(`/api/projects/${projectId}/tasks/${taskId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    // null clears the assignee; notify:true announces it in the Telegram group.
    body: JSON.stringify({ assignee_telegram_username: telegramUsername, notify: true }),
  });
}

export interface ProjectDetail {
  id: string;
  name: string;
  module_code: string | null;
  status: string;
  role: string;
  memberCount: number;
  goals: string | null;
}

export async function fetchProject(projectId: string): Promise<ProjectDetail> {
  return request<ProjectDetail>(`/api/projects/${projectId}`);
}

export async function updateProjectGoals(
  projectId: string,
  goals: string,
): Promise<ProjectDetail> {
  return request<ProjectDetail>(`/api/projects/${projectId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ goals }),
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
