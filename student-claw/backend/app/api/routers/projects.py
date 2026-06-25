"""Project listing, linking (Phase 3), task reads, and the RAG context endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.agent import run_agent
from app.api.deps import db_session, get_current_student, require_membership, resolve_project
from app.api.schemas import (
    AskIn,
    AskOut,
    ProjectLinkIn,
    ProjectOut,
)
from app.database.models import Project, ProjectLinkToken, Student, StudentProject, Task

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    student: Student = Depends(get_current_student),
    session: AsyncSession = Depends(db_session),
) -> list[ProjectOut]:
    rows = (
        await session.execute(
            select(Project, StudentProject.role)
            .join(StudentProject, StudentProject.project_id == Project.id)
            .where(StudentProject.student_id == student.id)
            .order_by(Project.created_at.desc())
        )
    ).all()
    return [
        ProjectOut(
            id=str(p.id),
            name=p.name,
            module_code=p.module_code,
            status=p.status.value,
            role=role.value,
            qdrant_point_count=p.qdrant_point_count,
        )
        for p, role in rows
    ]


@router.post("/link", status_code=status.HTTP_201_CREATED)
async def link_project(
    body: ProjectLinkIn,
    student: Student = Depends(get_current_student),
    session: AsyncSession = Depends(db_session),
) -> dict[str, bool]:
    """Phase 3: persist a short-lived link token minted by the BFF."""
    project = await session.scalar(
        select(Project).where(Project.project_key == body.project_key)
    )
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No project matches that key.")
    if not student.telegram_username:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Add your Telegram username to your account before linking.",
        )

    existing = await session.scalar(
        select(StudentProject).where(
            StudentProject.project_id == project.id,
            StudentProject.student_id == student.id,
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already linked to this project.")

    session.add(
        ProjectLinkToken(
            token=body.token,
            chat_id=project.chat_id,
            project_id=project.id,
            expires_at=body.expires_at,
        )
    )
    await session.commit()
    return {"ok": True}


@router.get("/{project_id}/tasks")
async def list_tasks(
    project_id: str,
    student: Student = Depends(get_current_student),
    session: AsyncSession = Depends(db_session),
) -> dict[str, list[dict]]:
    project = await resolve_project(project_id, session)
    await require_membership(project, student, session)

    tasks = (
        await session.scalars(
            select(Task)
            .options(selectinload(Task.assignee))
            .where(Task.project_id == project.id, Task.deleted_at.is_(None))
            .order_by(Task.created_at.desc())
        )
    ).all()

    return {
        "tasks": [
            {
                "id": str(t.id),
                "title": t.title,
                "description": t.description,
                "status": t.status.value,
                "priority": t.priority,
                "assignee": (
                    {
                        "id": str(t.assignee.id),
                        "displayName": t.assignee.display_name,
                        "telegramUsername": t.assignee.telegram_username,
                    }
                    if t.assignee
                    else None
                ),
                "deadlineTitle": (t.task_metadata or {}).get("related_deadline_title"),
            }
            for t in tasks
        ]
    }


@router.post("/{project_id}/context", response_model=AskOut)
async def ask_context(
    project_id: str,
    body: AskIn,
    student: Student = Depends(get_current_student),
    session: AsyncSession = Depends(db_session),
) -> AskOut:
    project = await resolve_project(project_id, session)
    await require_membership(project, student, session)
    answer = await run_agent(project.chat_id, body.query)
    return AskOut(answer_html=answer)
