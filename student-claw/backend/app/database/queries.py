"""
Aggregation queries for the contribution metrics dashboard (blueprint §6.4).

Produces a payload structured for the frontend radar + sparkline widgets:
per member a latest score, the radar axes (messages sent, files uploaded,
tasks completed), and the full score history for the sparkline.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    ContributionMetric,
    Deadline,
    MessageLog,
    Project,
    Student,
    StudentProject,
    Task,
    TaskStatus,
)


async def get_project_members(
    session: AsyncSession, project_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Real team roster for a project."""
    rows = (
        await session.execute(
            select(Student, StudentProject.role)
            .join(StudentProject, StudentProject.student_id == Student.id)
            .where(StudentProject.project_id == project_id)
            .order_by(StudentProject.joined_at.asc())
        )
    ).all()
    return [
        {
            "studentId": str(s.id),
            "displayName": s.display_name,
            "telegramUsername": s.telegram_username,
            "role": role.value,
        }
        for s, role in rows
    ]


async def get_student_overview(
    session: AsyncSession, student: Student
) -> dict[str, Any]:
    """
    Aggregated home-page payload for a student: their projects (with member
    counts), upcoming deadlines across those projects, and their personal
    to-do list (open tasks assigned to them).
    """
    membership_rows = (
        await session.execute(
            select(Project, StudentProject.role)
            .join(StudentProject, StudentProject.project_id == Project.id)
            .where(StudentProject.student_id == student.id)
            .order_by(Project.created_at.desc())
        )
    ).all()

    project_ids = [p.id for p, _ in membership_rows]
    name_by_id = {p.id: p.name for p, _ in membership_rows}

    # Member count per project, in one grouped query.
    counts: dict[uuid.UUID, int] = {}
    if project_ids:
        count_rows = (
            await session.execute(
                select(StudentProject.project_id, func.count())
                .where(StudentProject.project_id.in_(project_ids))
                .group_by(StudentProject.project_id)
            )
        ).all()
        counts = {pid: int(c) for pid, c in count_rows}

    projects = [
        {
            "id": str(p.id),
            "name": p.name,
            "moduleCode": p.module_code,
            "status": p.status.value,
            "role": role.value,
            "memberCount": counts.get(p.id, 1),
        }
        for p, role in membership_rows
    ]

    # Deadlines across all my projects (soonest first).
    deadlines: list[dict[str, Any]] = []
    todos: list[dict[str, Any]] = []
    if project_ids:
        deadline_rows = (
            await session.scalars(
                select(Deadline)
                .where(Deadline.project_id.in_(project_ids))
                .order_by(Deadline.due_date.asc())
                .limit(50)
            )
        ).all()
        deadlines = [
            {
                "id": str(d.id),
                "title": d.title,
                "dueDate": d.due_date,
                "projectId": str(d.project_id),
                "projectName": name_by_id.get(d.project_id, "Project"),
                "isConfirmed": d.is_confirmed,
            }
            for d in deadline_rows
        ]

        # My open tasks across all projects (the to-do list).
        todo_rows = (
            await session.scalars(
                select(Task)
                .where(
                    Task.assigned_to_student_id == student.id,
                    Task.status.in_([TaskStatus.pending, TaskStatus.in_progress]),
                    Task.deleted_at.is_(None),
                )
                .order_by(Task.priority.asc(), Task.created_at.desc())
            )
        ).all()
        todos = [
            {
                "id": str(t.id),
                "title": t.title,
                "status": t.status.value,
                "priority": t.priority,
                "projectId": str(t.project_id),
                "projectName": name_by_id.get(t.project_id, "Project"),
            }
            for t in todo_rows
        ]

    return {
        "displayName": student.display_name,
        "username": student.username,
        "telegramVerified": student.telegram_user_id is not None,
        "projects": projects,
        "deadlines": deadlines,
        "todos": todos,
    }


async def _radar_counts(
    session: AsyncSession, project_id: uuid.UUID, student: Student
) -> dict[str, int]:
    """Compute the three radar axes from source-of-truth tables."""
    messages_sent = 0
    files_uploaded = 0
    if student.telegram_user_id is not None:
        messages_sent = (
            await session.scalar(
                select(func.count())
                .select_from(MessageLog)
                .where(
                    MessageLog.project_id == project_id,
                    MessageLog.sender_telegram_user_id == student.telegram_user_id,
                    MessageLog.deleted_at.is_(None),
                )
            )
        ) or 0
        files_uploaded = (
            await session.scalar(
                select(func.count())
                .select_from(MessageLog)
                .where(
                    MessageLog.project_id == project_id,
                    MessageLog.sender_telegram_user_id == student.telegram_user_id,
                    MessageLog.content_type.in_(["image", "document"]),
                    MessageLog.deleted_at.is_(None),
                )
            )
        ) or 0

    tasks_completed = (
        await session.scalar(
            select(func.count())
            .select_from(Task)
            .where(
                Task.project_id == project_id,
                Task.assigned_to_student_id == student.id,
                Task.status == TaskStatus.done,
                Task.deleted_at.is_(None),
            )
        )
    ) or 0

    return {
        "messagesSent": int(messages_sent),
        "filesUploaded": int(files_uploaded),
        "tasksCompleted": int(tasks_completed),
    }


async def get_contributions_payload(
    session: AsyncSession, project_id: uuid.UUID
) -> dict[str, Any]:
    """Assemble the full contributions payload for a project."""
    rows = (
        await session.execute(
            select(Student, StudentProject.role)
            .join(StudentProject, StudentProject.student_id == Student.id)
            .where(StudentProject.project_id == project_id)
        )
    ).all()

    members: list[dict[str, Any]] = []
    for student, _role in rows:
        metrics = (
            await session.scalars(
                select(ContributionMetric)
                .where(
                    ContributionMetric.project_id == project_id,
                    ContributionMetric.student_id == student.id,
                )
                .order_by(ContributionMetric.scored_at.asc())
            )
        ).all()

        history = [
            {"scoredAt": m.scored_at, "score": float(m.score_value)} for m in metrics
        ]
        latest = metrics[-1] if metrics else None

        members.append(
            {
                "studentId": str(student.id),
                "displayName": student.display_name,
                "telegramUsername": student.telegram_username,
                "latestScore": float(latest.score_value) if latest else None,
                "reason": latest.score_reason if latest else None,
                "radar": await _radar_counts(session, project_id, student),
                "history": history,
            }
        )

    return {"projectId": str(project_id), "members": members}
