"""
Best-effort real-time event publishing (blueprint §4.2).

The web dashboard listens on Redis Pub/Sub channels `project_updates:{project_id}`
and fans events out over SSE. The bot publishes domain events here. Publishing
is best-effort: if Redis is unavailable or unconfigured, we log and continue —
a dropped real-time notification must never break message ingestion.

The full SSE replay/ordering machinery lives in the Next.js + FastAPI layer;
this module only needs to emit.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("student_claw.bot.events")

_REDIS_URL = os.getenv("REDIS_URL")

# Lazily-initialised redis.asyncio client (singleton). Optional dependency:
# if redis isn't installed or REDIS_URL is unset, publishing is a no-op.
_redis_client: Any | None = None
_redis_unavailable = False


async def _get_redis() -> Any | None:
    global _redis_client, _redis_unavailable
    if _redis_unavailable or not _REDIS_URL:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as aioredis  # type: ignore

        _redis_client = aioredis.from_url(_REDIS_URL, decode_responses=True)
        return _redis_client
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.warning("Redis unavailable, real-time events disabled: %s", exc)
        _redis_unavailable = True
        return None


def _channel(project_id: str) -> str:
    return f"project_updates:{project_id}"


# Dedicated channel the bot process subscribes to in order to push messages
# into a Telegram group (e.g. manual web delegations — Requirement 3).
BOT_NOTIFICATION_CHANNEL = "bot_notifications"


async def publish_bot_notification(chat_id: int, text: str) -> None:
    """Ask the bot process to send `text` (Telegram HTML) into `chat_id`."""
    redis = await _get_redis()
    if redis is None:
        return
    try:
        await redis.publish(
            BOT_NOTIFICATION_CHANNEL, json.dumps({"chat_id": chat_id, "text": text})
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to publish bot notification for %s: %s", chat_id, exc)


async def publish_project_event(
    project_id: str,
    event_type: str,
    payload: dict[str, Any],
    *,
    triggered_by: str = "bot",
) -> None:
    """
    Publish an event to a project's channel. Never raises.

    Args:
        project_id:   UUID string of the project.
        event_type:   e.g. "member_joined", "task_created", "cache_cleared".
        payload:      JSON-serialisable event body.
        triggered_by: provenance tag ("bot", "ai_agent", "web", ...).
    """
    redis = await _get_redis()
    if redis is None:
        return
    message = {
        "type": event_type,
        "triggered_by": triggered_by,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    try:
        await redis.publish(_channel(project_id), json.dumps(message, default=str))
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to publish %s for project %s: %s", event_type, project_id, exc)
