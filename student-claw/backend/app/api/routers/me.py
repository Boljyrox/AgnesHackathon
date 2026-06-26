"""Current-student aggregate endpoints (home-page task manager)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_student
from app.api.schemas import StudentOverviewOut
from app.database.models import Student
from app.database.queries import get_student_overview

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/overview", response_model=StudentOverviewOut)
async def overview(
    student: Student = Depends(get_current_student),
    session: AsyncSession = Depends(db_session),
) -> StudentOverviewOut:
    payload = await get_student_overview(session, student)
    return StudentOverviewOut.model_validate(payload)
