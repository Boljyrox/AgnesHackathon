"""Task mutation endpoint (Kanban status transitions)."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import db_session, get_current_student, require_membership, resolve_project
from app.api.schemas import TaskCreateIn, TaskOut, TaskPatchIn
from app.bot import events
from app.database.models import Student, StudentProject, Task, TaskSource, TaskStatus

router = APIRouter(prefix="/projects", tags=["tasks"])


def _serialize(task: Task) -> TaskOut:
    return TaskOut(
        id=str(task.id),
        title=task.title,
        description=task.description,
        status=task.status.value,  # type: ignore[arg-type]
        priority=task.priority,
        assignee=(
            {
                "id": str(task.assignee.id),
                "displayName": task.assignee.display_name,
                "telegramUsername": task.assignee.telegram_username,
            }
            if task.assignee
            else None
        ),
        deadlineTitle=(task.task_metadata or {}).get("related_deadline_title"),
    )


@router.post("/{project_id}/tasks", response_model=TaskOut, status_code=201)
async def create_task(
    project_id: str,
    body: TaskCreateIn,
    student: Student = Depends(get_current_student),
    session: AsyncSession = Depends(db_session),
) -> TaskOut:
    """Manually create a task (web task manager)."""
    project = await resolve_project(project_id, session)
    await require_membership(project, student, session)

    assignee_id = None
    if body.assignee_telegram_username:
        member = await session.scalar(
            select(Student)
            .join(StudentProject, StudentProject.student_id == Student.id)
            .where(
                StudentProject.project_id == project.id,
                Student.telegram_username.ilike(body.assignee_telegram_username.lstrip("@")),
            )
        )
        if member is not None:
            assignee_id = member.id

    task = Task(
        project_id=project.id,
        assigned_to_student_id=assignee_id,
        title=body.title,
        description=body.description,
        source=TaskSource.manual,
        status=TaskStatus(body.status),
        priority=body.priority,
    )
    session.add(task)
    await session.commit()
    task = await session.scalar(
        select(Task).options(selectinload(Task.assignee)).where(Task.id == task.id)
    )
    assert task is not None

    await events.publish_project_event(
        project_id=str(project.id),
        event_type="task_created",
        payload={"task_id": str(task.id)},
        triggered_by="web",
    )
    return _serialize(task)


@router.patch("/{project_id}/tasks/{task_id}", response_model=TaskOut)
async def patch_task(
    project_id: str,
    task_id: str,
    body: TaskPatchIn,
    student: Student = Depends(get_current_student),
    session: AsyncSession = Depends(db_session),
) -> TaskOut:
    project = await resolve_project(project_id, session)
    await require_membership(project, student, session)

    try:
        tid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found.")

    task = await session.scalar(
        select(Task).options(selectinload(Task.assignee)).where(Task.id == tid)
    )
    # Multi-tenant guard: a task from another project is invisible here.
    if task is None or task.project_id != project.id or task.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found.")

    fields = body.model_fields_set
    if "status" in fields and body.status is not None:
        task.status = TaskStatus(body.status)

    # Assignee change (a manual delegation). Track it so we can notify the group.
    delegated_to: Optional[Student] = None
    assignee_changed = False
    if "assignee_telegram_username" in fields:
        previous_assignee_id = task.assigned_to_student_id
        username = (body.assignee_telegram_username or "").lstrip("@").strip()
        if username:
            member = await session.scalar(
                select(Student)
                .join(StudentProject, StudentProject.student_id == Student.id)
                .where(
                    StudentProject.project_id == project.id,
                    Student.telegram_username.ilike(username),
                )
            )
            if member is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"@{username} is not a member of this project.",
                )
            task.assigned_to_student_id = member.id
            delegated_to = member
        else:
            task.assigned_to_student_id = None  # explicit unassign
        assignee_changed = task.assigned_to_student_id != previous_assignee_id

    await session.commit()
    task = await session.scalar(
        select(Task).options(selectinload(Task.assignee)).where(Task.id == tid)
    )
    assert task is not None

    # Always publish for the web SSE clients.
    await events.publish_project_event(
        project_id=str(project.id),
        event_type="task_updated",
        payload={
            "task_id": str(task.id),
            "status": task.status.value,
            "assignee": task.assignee.telegram_username if task.assignee else None,
        },
        triggered_by="web",
    )

    # Optionally notify the Telegram group of a manual delegation.
    if assignee_changed and body.notify and delegated_to is not None:
        handle = f"@{delegated_to.telegram_username}" if delegated_to.telegram_username else delegated_to.display_name
        by = f"@{student.telegram_username}" if student.telegram_username else student.display_name
        await events.publish_bot_notification(
            chat_id=project.chat_id,
            text=f"📋 <b>{handle}</b> was assigned \"<i>{task.title}</i>\" by {by} (via the web app).",
        )

    return _serialize(task)
