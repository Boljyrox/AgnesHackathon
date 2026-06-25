/**
 * Placeholder data for wiring up the dashboard UI before the task/context
 * endpoints land (Module 6). Team names per the Module 5 design note.
 */

import type { Member, Task } from "@/lib/domain";

export const PLACEHOLDER_MEMBERS: Member[] = [
  { id: "m1", displayName: "Lechu", telegramUsername: "lechu", role: "lead" },
  { id: "m2", displayName: "Ashok", telegramUsername: "ashok", role: "member" },
  { id: "m3", displayName: "Yibin", telegramUsername: "yibin", role: "member" },
  { id: "m4", displayName: "Marcus", telegramUsername: "marcus", role: "member" },
  { id: "m5", displayName: "Leonard", telegramUsername: "leonard", role: "observer" },
];

const [lechu, ashok, yibin, marcus, leonard] = PLACEHOLDER_MEMBERS;

export const PLACEHOLDER_TASKS: Task[] = [
  {
    id: "t1",
    title: "Draft system architecture diagram",
    status: "done",
    priority: 2,
    assignee: lechu,
    deadlineTitle: "Design Review",
  },
  {
    id: "t2",
    title: "Implement embedding worker",
    status: "in_progress",
    priority: 1,
    assignee: ashok,
    deadlineTitle: "Prototype Demo",
  },
  {
    id: "t3",
    title: "Wire up Google Calendar OAuth",
    status: "pending",
    priority: 2,
    assignee: yibin,
  },
  {
    id: "t4",
    title: "Write contribution scoring rubric",
    status: "pending",
    priority: 3,
    assignee: marcus,
  },
  {
    id: "t5",
    title: "Record prototype demo video",
    status: "in_progress",
    priority: 1,
    assignee: leonard,
    deadlineTitle: "Prototype Demo",
  },
  {
    id: "t6",
    title: "Evaluate Pinecone vs Qdrant",
    status: "dropped",
    priority: 3,
    assignee: lechu,
  },
  {
    id: "t7",
    title: "Set up CI for the backend",
    status: "pending",
    priority: 2,
    assignee: null,
  },
];
