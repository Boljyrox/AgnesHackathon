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
    status: TaskStatus


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
