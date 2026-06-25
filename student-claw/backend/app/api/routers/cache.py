"""Cache-cleanse endpoint (blueprint §5.3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import pipeline
from app.api.deps import db_session, get_current_student, require_lead, resolve_project
from app.api.schemas import ClearCacheIn, ClearCacheOut
from app.bot import events
from app.database.models import Student

router = APIRouter(prefix="/projects", tags=["cache"])


@router.post("/{project_id}/clearcache", response_model=ClearCacheOut)
async def clear_cache(
    project_id: str,
    body: ClearCacheIn,
    student: Student = Depends(get_current_student),
    session: AsyncSession = Depends(db_session),
) -> ClearCacheOut:
    project = await resolve_project(project_id, session)
    # Step 1: AUTHORIZATION CHECK — lead role required.
    await require_lead(project, student, session)

    try:
        result = await pipeline.clear_project_cache(
            str(project.id), include_files=body.include_files
        )
    except Exception as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, f"Cache cleanse failed: {exc}"
        )

    # Step 8: NOTIFY.
    await events.publish_project_event(
        project_id=str(project.id),
        event_type="cache_cleared",
        payload={"by": student.username, "files_deleted": result.files_deleted},
        triggered_by="web",
    )

    return ClearCacheOut(
        ok=result.ok,
        vectors_deleted=result.vectors_deleted,
        files_deleted=result.files_deleted,
        messages_soft_deleted=result.messages_soft_deleted,
        status=result.status,
    )
