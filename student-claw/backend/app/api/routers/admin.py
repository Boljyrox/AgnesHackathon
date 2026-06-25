"""
SUTD_Admin diagnostic endpoints (Requirement 1).

All routes are gated by the `require_admin` dependency (shared admin token in
the X-Admin-Token header). Provides Agnes AI request logs + Qdrant vector-store
inspection.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.clients import get_qdrant_client
from app.ai.config import collection_name
from app.api.deps import db_session, require_admin
from app.database.queries import get_ai_request_logs

logger = logging.getLogger("student_claw.api.admin")

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/ai-logs")
async def ai_logs(
    chat_id: Optional[int] = Query(default=None),
    kind: Optional[str] = Query(default=None, pattern="^(chat|embedding|vision)$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(db_session),
) -> dict[str, Any]:
    logs = await get_ai_request_logs(
        session, chat_id=chat_id, kind=kind, limit=limit, offset=offset
    )
    return {"logs": logs, "count": len(logs)}


@router.get("/qdrant/collections")
async def qdrant_collections() -> dict[str, Any]:
    """List every Qdrant collection with its point count."""
    client = get_qdrant_client()
    try:
        collections = await client.get_collections()
    except Exception as exc:
        logger.error("Qdrant list failed: %s", exc)
        return {"collections": [], "error": str(exc)}

    out: list[dict[str, Any]] = []
    for c in collections.collections:
        try:
            info = await client.count(collection_name=c.name, exact=True)
            count = info.count
        except Exception:
            count = None
        # Collection names are project_{chat_id}; surface the chat_id.
        chat_id = c.name.removeprefix("project_") if c.name.startswith("project_") else None
        out.append({"name": c.name, "chatId": chat_id, "pointCount": count})
    return {"collections": out}


@router.get("/qdrant/{chat_id}/points")
async def qdrant_points(
    chat_id: int,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Scroll the stored vectors for a chat_id and return their payloads."""
    client = get_qdrant_client()
    name = collection_name(chat_id)
    if not await client.collection_exists(name):
        return {"collection": name, "points": [], "note": "Collection does not exist."}

    points, _next = await client.scroll(
        collection_name=name,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return {
        "collection": name,
        "points": [
            {
                "id": str(p.id),
                "messageLogId": (p.payload or {}).get("message_log_id"),
                "contentType": (p.payload or {}).get("content_type"),
                "sender": (p.payload or {}).get("sender_username"),
                "receivedAt": (p.payload or {}).get("received_at"),
                "source": (p.payload or {}).get("source_filename"),
                "chunkIndex": (p.payload or {}).get("chunk_index"),
                "textSnippet": (p.payload or {}).get("text_snippet"),
            }
            for p in points
        ],
    }
