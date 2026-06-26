"""Contribution metrics endpoint feeding the radar + sparkline widgets."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_student, require_membership, resolve_project
from app.api.schemas import ContributionsOut
from app.database.models import Student
from app.database.queries import get_contributions_payload

router = APIRouter(prefix="/projects", tags=["contributions"])


@router.get("/{project_id}/contributions", response_model=ContributionsOut)
async def get_contributions(
    project_id: str,
    student: Student = Depends(get_current_student),
    session: AsyncSession = Depends(db_session),
) -> ContributionsOut:
    project = await resolve_project(project_id, session)
    await require_membership(project, student, session)
    payload = await get_contributions_payload(session, project.id)
    return ContributionsOut.model_validate(payload)
