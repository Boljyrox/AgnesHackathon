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
    MessageLog,
    Project,
    Student,
    StudentProject,
    Task,
    TaskStatus,
)


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
