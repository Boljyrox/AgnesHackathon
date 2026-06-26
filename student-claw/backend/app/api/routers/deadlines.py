"""Deadline read/create/confirm endpoints + Google Calendar sync hook."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.calendar import sync_deadline_to_calendar
from app.api.deps import db_session, get_current_student, require_membership, resolve_project
from app.api.schemas import DeadlineConfirmIn, DeadlineCreateIn, DeadlineOut
from app.database.models import Deadline, DeadlineExtractedBy, Student

router = APIRouter(prefix="/projects", tags=["deadlines"])


def _serialize(d: Deadline) -> DeadlineOut:
    return DeadlineOut(
        id=str(d.id),
        title=d.title,
        due_date=d.due_date,
        extracted_by=d.extracted_by.value,
        is_confirmed=d.is_confirmed,
        google_calendar_event_id=d.google_calendar_event_id,
        task_id=str(d.task_id) if d.task_id else None,
    )


@router.get("/{project_id}/deadlines")
async def list_deadlines(
    project_id: str,
    student: Student = Depends(get_current_student),
    session: AsyncSession = Depends(db_session),
) -> dict[str, list[DeadlineOut]]:
    project = await resolve_project(project_id, session)
    await require_membership(project, student, session)
    rows = (
        await session.scalars(
            select(Deadline)
            .where(Deadline.project_id == project.id)
            .order_by(Deadline.due_date.asc())
        )
    ).all()
    return {"deadlines": [_serialize(d) for d in rows]}


@router.post("/{project_id}/deadlines", response_model=DeadlineOut, status_code=201)
async def create_deadline(
    project_id: str,
    body: DeadlineCreateIn,
    background: BackgroundTasks,
    student: Student = Depends(get_current_student),
    session: AsyncSession = Depends(db_session),
) -> DeadlineOut:
    project = await resolve_project(project_id, session)
    await require_membership(project, student, session)

    deadline = Deadline(
        project_id=project.id,
        task_id=uuid.UUID(body.task_id) if body.task_id else None,
        title=body.title,
        due_date=body.due_date,
        extracted_by=DeadlineExtractedBy.manual,
        is_confirmed=body.confirm,
    )
    session.add(deadline)
    await session.commit()
    await session.refresh(deadline)

    # Sync hook: push to the creator's calendar when confirmed.
    if deadline.is_confirmed and student.google_calendar_refresh_token:
        background.add_task(sync_deadline_to_calendar, str(deadline.id), str(student.id))

    return _serialize(deadline)


@router.patch("/{project_id}/deadlines/{deadline_id}", response_model=DeadlineOut)
async def confirm_deadline(
    project_id: str,
    deadline_id: str,
    body: DeadlineConfirmIn,
    background: BackgroundTasks,
    student: Student = Depends(get_current_student),
    session: AsyncSession = Depends(db_session),
) -> DeadlineOut:
    """Confirm an AI-extracted deadline → triggers the calendar sync hook (§6.5)."""
    project = await resolve_project(project_id, session)
    await require_membership(project, student, session)

    try:
        did = uuid.UUID(deadline_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deadline not found.")

    deadline = await session.get(Deadline, did)
    if deadline is None or deadline.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deadline not found.")

    deadline.is_confirmed = body.is_confirmed
    await session.commit()
    await session.refresh(deadline)

    if deadline.is_confirmed and student.google_calendar_refresh_token:
        background.add_task(sync_deadline_to_calendar, str(deadline.id), str(student.id))

    return _serialize(deadline)
