"""
Strict Pydantic v2 contracts for the web API.

Inputs use `extra="forbid"` so malformed/extra fields are rejected at the edge.
Frontend-facing outputs are shaped to match the TypeScript interfaces in
frontend/src/lib (camelCase where the React layer consumes them directly).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

TaskStatus = Literal["pending", "in_progress", "done", "dropped"]


class _StrictIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---- auth -----------------------------------------------------------------
class RegisterIn(_StrictIn):
    display_name: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=256)
    telegram_username: Optional[str] = Field(default=None, max_length=50)


class LoginIn(_StrictIn):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=256)


class RefreshIn(_StrictIn):
    refresh_token: str = Field(min_length=10)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str


# ---- projects -------------------------------------------------------------
class ProjectOut(BaseModel):
    id: str
    name: str
    module_code: Optional[str]
    status: str
    role: str
    qdrant_point_count: int


class ProjectLinkIn(_StrictIn):
    project_key: str = Field(min_length=8, max_length=64)
    token: str = Field(min_length=16, max_length=64)
    expires_at: datetime


# ---- tasks ----------------------------------------------------------------
class AssigneeOut(BaseModel):
    id: str
    displayName: str
    telegramUsername: Optional[str]


class TaskOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    status: TaskStatus
    priority: int
    assignee: Optional[AssigneeOut]
    deadlineTitle: Optional[str]


class TaskPatchIn(_StrictIn):
    # Both optional — send either or both. Use model_fields_set to tell whether
    # a field was provided (so assignee can be explicitly cleared with null).
    status: Optional[TaskStatus] = None
    assignee_telegram_username: Optional[str] = None
    # Whether the bot should announce a manual (re)assignment in the group.
    notify: bool = True


class ProjectDetailOut(BaseModel):
    id: str
    name: str
    module_code: Optional[str]
    status: str
    role: str
    memberCount: int
    goals: Optional[str]


class ProjectGoalsIn(_StrictIn):
    goals: Optional[str] = Field(default=None, max_length=4000)


class TaskCreateIn(_StrictIn):
    title: str = Field(min_length=1, max_length=500)
    description: Optional[str] = None
    priority: int = Field(default=2, ge=1, le=3)
    status: TaskStatus = "pending"
    assignee_telegram_username: Optional[str] = None


# ---- members & overview ---------------------------------------------------
class MemberOut(BaseModel):
    studentId: str
    displayName: str
    telegramUsername: Optional[str]
    role: str


class OverviewProject(BaseModel):
    id: str
    name: str
    moduleCode: Optional[str]
    status: str
    role: str
    memberCount: int


class OverviewDeadline(BaseModel):
    id: str
    title: str
    dueDate: datetime
    projectId: str
    projectName: str
    isConfirmed: bool


class OverviewTodo(BaseModel):
    id: str
    title: str
    status: str
    priority: int
    projectId: str
    projectName: str


class StudentOverviewOut(BaseModel):
    displayName: str
    username: str
    telegramVerified: bool
    projects: list[OverviewProject]
    deadlines: list[OverviewDeadline]
    todos: list[OverviewTodo]


# ---- deadlines ------------------------------------------------------------
class DeadlineOut(BaseModel):
    id: str
    title: str
    due_date: datetime
    extracted_by: str
    is_confirmed: bool
    google_calendar_event_id: Optional[str]
    task_id: Optional[str]


class DeadlineCreateIn(_StrictIn):
    title: str = Field(min_length=1, max_length=500)
    due_date: datetime
    task_id: Optional[str] = None
    # When true (default for manual creation) the deadline is immediately
    # confirmed and pushed to the user's Google Calendar.
    confirm: bool = True


class DeadlineConfirmIn(_StrictIn):
    is_confirmed: bool = True


# ---- context / agent ------------------------------------------------------
class AskIn(_StrictIn):
    query: str = Field(min_length=1, max_length=2000)


class AskOut(BaseModel):
    answer_html: str


# ---- cache cleanse --------------------------------------------------------
class ClearCacheIn(_StrictIn):
    include_files: bool = False


class ClearCacheOut(BaseModel):
    ok: bool
    vectors_deleted: bool
    files_deleted: bool
    messages_soft_deleted: int
    status: str


# ---- google calendar ------------------------------------------------------
class GoogleCalendarIn(_StrictIn):
    encrypted_refresh_token: str = Field(min_length=16)


# ---- contributions --------------------------------------------------------
class ContributionRadar(BaseModel):
    messagesSent: int
    filesUploaded: int
    tasksCompleted: int


class ContributionHistoryPoint(BaseModel):
    scoredAt: datetime
    score: float


class ContributionMemberOut(BaseModel):
    studentId: str
    displayName: str
    telegramUsername: Optional[str]
    latestScore: Optional[float]
    reason: Optional[str]
    radar: ContributionRadar
    history: list[ContributionHistoryPoint]


class ContributionsOut(BaseModel):
    projectId: str
    members: list[ContributionMemberOut]
