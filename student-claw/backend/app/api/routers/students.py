"""Student self-service endpoints (Google Calendar token storage)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_student
from app.api.schemas import GoogleCalendarIn
from app.database.models import Student

router = APIRouter(prefix="/students", tags=["students"])


@router.patch("/me/google-calendar")
async def store_google_calendar_token(
    body: GoogleCalendarIn,
    student: Student = Depends(get_current_student),
    session: AsyncSession = Depends(db_session),
) -> dict[str, bool]:
    """
    Persist the AES-256-GCM-encrypted refresh token produced by the BFF callback
    (blueprint §6.5). The plaintext token never touches our database or logs.
    """
    student.google_calendar_refresh_token = body.encrypted_refresh_token
    student.google_calendar_linked_at = func.now()  # type: ignore[assignment]
    await session.commit()
    return {"ok": True}
