"""
Google Calendar v3 integration (blueprint §6.5).

The user's refresh token is stored encrypted (AES-256-GCM). To sync a deadline
we decrypt it, exchange it for a short-lived access token, and create/patch the
calendar event. Access tokens are never persisted (blueprint §8.1).
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

import httpx
from sqlalchemy import select

from app.core.config import (
    GOOGLE_CALENDAR_API,
    GOOGLE_TOKEN_URI,
    get_web_settings,
)
from app.core.security import decrypt_secret
from app.database.connection import session_scope
from app.database.models import Deadline, Student

logger = logging.getLogger("student_claw.ai.calendar")


class CalendarSyncError(Exception):
    """Raised when a deadline cannot be synced to Google Calendar."""


async def _access_token_from_refresh(refresh_token: str) -> str:
    settings = get_web_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            GOOGLE_TOKEN_URI,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code != 200:
        raise CalendarSyncError(f"Token refresh failed ({resp.status_code}).")
    token = resp.json().get("access_token")
    if not token:
        raise CalendarSyncError("No access_token in Google token response.")
    return token


def _event_body(deadline: Deadline) -> dict:
    start = deadline.due_date
    end = start + timedelta(hours=1)
    return {
        "summary": f"[Student Claw] {deadline.title}",
        "description": "Deadline tracked by Student Claw.",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        "reminders": {"useDefault": True},
    }


async def _upsert_event(
    access_token: str, deadline: Deadline, existing_event_id: str | None
) -> str:
    headers = {"Authorization": f"Bearer {access_token}"}
    body = _event_body(deadline)
    async with httpx.AsyncClient(timeout=15) as client:
        if existing_event_id:
            resp = await client.patch(
                f"{GOOGLE_CALENDAR_API}/calendars/primary/events/{existing_event_id}",
                headers=headers,
                json=body,
            )
        else:
            resp = await client.post(
                f"{GOOGLE_CALENDAR_API}/calendars/primary/events",
                headers=headers,
                json=body,
            )
    if resp.status_code not in (200, 201):
        raise CalendarSyncError(f"Calendar upsert failed ({resp.status_code}).")
    return resp.json()["id"]


async def sync_deadline_to_calendar(deadline_id: str, student_id: str) -> None:
    """
    Background hook (blueprint §6.5): push/patch a confirmed deadline to the
    confirming student's Google Calendar. Best-effort — failures are logged, not
    raised, so the confirmation request itself always succeeds.
    """
    try:
        async with session_scope() as session:
            student = await session.get(Student, uuid.UUID(student_id))
            if student is None or not student.google_calendar_refresh_token:
                logger.info("No Google Calendar link for student %s; skipping.", student_id)
                return

            deadline = await session.get(Deadline, uuid.UUID(deadline_id))
            if deadline is None or not deadline.is_confirmed:
                logger.info("Deadline %s missing/unconfirmed; skipping sync.", deadline_id)
                return

            refresh_token = decrypt_secret(student.google_calendar_refresh_token)
            access_token = await _access_token_from_refresh(refresh_token)
            event_id = await _upsert_event(
                access_token, deadline, deadline.google_calendar_event_id
            )
            deadline.google_calendar_event_id = event_id
            logger.info("Synced deadline %s → calendar event %s.", deadline_id, event_id)
    except CalendarSyncError as exc:
        logger.error("Calendar sync error for deadline %s: %s", deadline_id, exc)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected calendar sync failure for %s: %s", deadline_id, exc)
