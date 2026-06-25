"""
Database service layer for the bot.

These functions encapsulate every DB mutation the Telegram handlers perform,
each inside a single `session_scope` transaction (Module 1 utility). Handlers
stay thin and free of SQLAlchemy details. Return values are plain dataclasses
of primitives so callers never touch detached ORM instances after the session
closes.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select

from app.bot.keys import derive_project_key, vector_namespace_for
from app.database.connection import session_scope
from app.database.models import (
    ContentType,
    LinkedVia,
    MemberRole,
    MessageLog,
    Project,
    ProjectLinkToken,
    ProjectStatus,
    Student,
    StudentProject,
    Task,
    TaskStatus,
)


# ---------------------------------------------------------------------------
# Result objects
# ---------------------------------------------------------------------------
@dataclass
class ProjectResult:
    project_id: str
    chat_id: int
    name: str
    project_key: str
    vector_namespace: str
    created: bool


@dataclass
class VerifyResult:
    ok: bool
    # One of: "verified", "invalid_token", "expired", "consumed",
    # "wrong_chat", "no_username", "unknown_student"
    reason: str
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    student_id: Optional[str] = None
    already_member: bool = False


# ---------------------------------------------------------------------------
# Project registration (Phase 2)
# ---------------------------------------------------------------------------
async def get_or_create_project(chat_id: int, name: str) -> ProjectResult:
    """
    Idempotently fetch-or-create the Project for a Telegram chat_id.

    The project_key and vector_namespace are derived deterministically so this
    is safe to call repeatedly (e.g. bot re-added to the same group).
    """
    async with session_scope() as session:
        existing = await session.scalar(
            select(Project).where(Project.chat_id == chat_id)
        )
        if existing is not None:
            return ProjectResult(
                project_id=str(existing.id),
                chat_id=existing.chat_id,
                name=existing.name,
                project_key=existing.project_key,
                vector_namespace=existing.vector_namespace,
                created=False,
            )

        project = Project(
            chat_id=chat_id,
            name=name or f"Project {chat_id}",
            project_key=derive_project_key(chat_id),
            vector_namespace=vector_namespace_for(chat_id),
        )
        session.add(project)
        await session.flush()  # populate project.id within the transaction
        return ProjectResult(
            project_id=str(project.id),
            chat_id=project.chat_id,
            name=project.name,
            project_key=project.project_key,
            vector_namespace=project.vector_namespace,
            created=True,
        )


# ---------------------------------------------------------------------------
# Verification (Phase 4)
# ---------------------------------------------------------------------------
async def consume_link_token(
    *,
    token: str,
    chat_id: int,
    telegram_user_id: int,
    telegram_username: Optional[str],
) -> VerifyResult:
    """
    Validate and consume a project_link_token, then link the sender's student
    account to the project. Single transaction; rolls back on any failure.

    Matching strategy (per blueprint Phase 4): the sender is matched to a
    `students` row by `telegram_username` captured at web registration, then
    their `telegram_user_id` is recorded.
    """
    now = datetime.now(timezone.utc)

    async with session_scope() as session:
        token_row = await session.scalar(
            select(ProjectLinkToken).where(ProjectLinkToken.token == token)
        )
        if token_row is None:
            return VerifyResult(ok=False, reason="invalid_token")
        if token_row.consumed_at is not None:
            return VerifyResult(ok=False, reason="consumed")
        if token_row.expires_at <= now:
            return VerifyResult(ok=False, reason="expired")
        if token_row.chat_id != chat_id:
            # Token must be redeemed inside the group it was issued for.
            return VerifyResult(ok=False, reason="wrong_chat")

        if not telegram_username:
            return VerifyResult(ok=False, reason="no_username")

        # Telegram usernames are case-insensitive; match on lowercase.
        student = await session.scalar(
            select(Student).where(
                Student.telegram_username.ilike(telegram_username)
            )
        )
        if student is None:
            return VerifyResult(ok=False, reason="unknown_student")

        # Bind the Telegram numeric identity to the account.
        student.telegram_user_id = telegram_user_id

        project = await session.get(Project, token_row.project_id)
        project_name = project.name if project else None

        # Idempotent membership insert.
        existing_membership = await session.scalar(
            select(StudentProject).where(
                StudentProject.student_id == student.id,
                StudentProject.project_id == token_row.project_id,
            )
        )
        already_member = existing_membership is not None
        if not already_member:
            session.add(
                StudentProject(
                    student_id=student.id,
                    project_id=token_row.project_id,
                    role=MemberRole.member,
                    linked_via=LinkedVia.telegram,
                )
            )

        # Single-use enforcement.
        token_row.consumed_at = now
        token_row.consumed_by_student_id = student.id

        return VerifyResult(
            ok=True,
            reason="verified",
            project_id=str(token_row.project_id),
            project_name=project_name,
            student_id=str(student.id),
            already_member=already_member,
        )


# ---------------------------------------------------------------------------
# Passive message logging (RAG foundation)
# ---------------------------------------------------------------------------
async def log_incoming_message(
    *,
    chat_id: int,
    telegram_message_id: int,
    content_type: ContentType,
    sender_telegram_user_id: Optional[int],
    sender_telegram_username: Optional[str],
    received_at: datetime,
    raw_text: Optional[str] = None,
    file_mime_type: Optional[str] = None,
    file_storage_path: Optional[str] = None,
) -> Optional[str]:
    """
    Persist a message into `message_logs` (is_vectorized=False) and keep the
    project roster current.

    Returns the new message_log id (str), or None if no project exists for the
    chat (the bot has not been registered in this group yet).

    Roster maintenance: if the sender maps to a known student (by
    telegram_user_id) who is not yet a project member, a membership row is
    created so the dashboard reflects active participants.
    """
    async with session_scope() as session:
        project = await session.scalar(
            select(Project).where(Project.chat_id == chat_id)
        )
        if project is None:
            return None

        # Keep the roster up to date for already-verified students.
        if sender_telegram_user_id is not None:
            student = await session.scalar(
                select(Student).where(
                    Student.telegram_user_id == sender_telegram_user_id
                )
            )
            if student is not None:
                membership = await session.scalar(
                    select(StudentProject).where(
                        StudentProject.student_id == student.id,
                        StudentProject.project_id == project.id,
                    )
                )
                if membership is None:
                    session.add(
                        StudentProject(
                            student_id=student.id,
                            project_id=project.id,
                            role=MemberRole.member,
                            linked_via=LinkedVia.telegram,
                        )
                    )

        log = MessageLog(
            id=uuid.uuid4(),
            chat_id=chat_id,
            project_id=project.id,
            telegram_message_id=telegram_message_id,
            sender_telegram_username=sender_telegram_username,
            sender_telegram_user_id=sender_telegram_user_id,
            content_type=content_type,
            raw_text=raw_text,
            file_mime_type=file_mime_type,
            file_storage_path=file_storage_path,
            is_vectorized=False,
            received_at=received_at,
        )
        session.add(log)
        await session.flush()
        return str(log.id)


# ---------------------------------------------------------------------------
# Project mutation helpers (Requirement 4 commands)
# ---------------------------------------------------------------------------
async def resolve_project_id(chat_id: int) -> Optional[str]:
    async with session_scope() as session:
        project = await session.scalar(select(Project).where(Project.chat_id == chat_id))
        return str(project.id) if project else None


async def get_project_goals(chat_id: int) -> tuple[bool, Optional[str]]:
    """(exists, goals) for the chat's project."""
    async with session_scope() as session:
        project = await session.scalar(select(Project).where(Project.chat_id == chat_id))
        if project is None:
            return (False, None)
        return (True, project.goals)


async def update_project_goals(chat_id: int, goals: str) -> bool:
    async with session_scope() as session:
        project = await session.scalar(select(Project).where(Project.chat_id == chat_id))
        if project is None:
            return False
        project.goals = goals.strip() or None
        return True


async def set_project_status(chat_id: int, status: ProjectStatus) -> bool:
    async with session_scope() as session:
        project = await session.scalar(select(Project).where(Project.chat_id == chat_id))
        if project is None:
            return False
        project.status = status
        return True


async def get_task_ledger(chat_id: int) -> Optional[dict]:
    """Completed vs outstanding vs dropped task titles for /celebrate."""
    async with session_scope() as session:
        project = await session.scalar(select(Project).where(Project.chat_id == chat_id))
        if project is None:
            return None
        tasks = (
            await session.scalars(
                select(Task).where(Task.project_id == project.id, Task.deleted_at.is_(None))
            )
        ).all()
    ledger: dict[str, list[str]] = {"completed": [], "outstanding": [], "dropped": []}
    for t in tasks:
        if t.status == TaskStatus.done:
            ledger["completed"].append(t.title)
        elif t.status == TaskStatus.dropped:
            ledger["dropped"].append(t.title)
        else:
            ledger["outstanding"].append(t.title)
    return ledger


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text or "").strip()


async def log_agent_interaction(
    *,
    chat_id: int,
    asker_username: Optional[str],
    asker_user_id: Optional[int],
    question: str,
    answer: str,
    q_message_id: int,
    a_message_id: int,
) -> None:
    """
    Persist an agent Q&A turn into message_logs so it becomes part of the
    short-term memory window (Requirement 2). Slash-command questions are
    otherwise dropped (commands aren't captured by the passive listener), which
    is why the agent "forgot" previous questions. NOT enqueued for embedding.
    """
    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        project = await session.scalar(
            select(Project).where(Project.chat_id == chat_id)
        )
        if project is None:
            return

        # User question.
        session.add(
            MessageLog(
                id=uuid.uuid4(),
                chat_id=chat_id,
                project_id=project.id,
                telegram_message_id=q_message_id,
                sender_telegram_username=asker_username,
                sender_telegram_user_id=asker_user_id,
                content_type=ContentType.text,
                raw_text=question,
                is_vectorized=False,
                received_at=now,
            )
        )
        # Agnes answer (plain text; HTML stripped for memory readability).
        session.add(
            MessageLog(
                id=uuid.uuid4(),
                chat_id=chat_id,
                project_id=project.id,
                telegram_message_id=a_message_id,
                sender_telegram_username="Agnes",
                content_type=ContentType.text,
                raw_text=_strip_html(answer),
                is_vectorized=False,
                received_at=now,
            )
        )
