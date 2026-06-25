"""Task mutation endpoint (Kanban status transitions)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import db_session, get_current_student, require_membership, resolve_project
from app.api.schemas import TaskOut, TaskPatchIn
from app.bot import events
from app.database.models import Student, Task, TaskStatus

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

    task.status = TaskStatus(body.status)
    await session.commit()
    await session.refresh(task)

    await events.publish_project_event(
        project_id=str(project.id),
        event_type="task_updated",
        payload={"task_id": str(task.id), "status": task.status.value},
        triggered_by="web",
    )
    return _serialize(task)
