"""
Lightweight Redis job queue for the embedding pipeline (blueprint §5.1).

The bot process enqueues a small JSON job per persisted message; the embedding
worker (pipeline.run_worker) consumes them. This module imports only
`redis.asyncio` + json so the bot stays light. Heavy work happens in the worker.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from app.ai.config import EMBED_DEAD_LETTER_KEY, EMBED_QUEUE_KEY

logger = logging.getLogger("student_claw.ai.queue")

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_client: Any | None = None


def _redis() -> Any:
    global _client
    if _client is None:
        import redis.asyncio as aioredis  # type: ignore

        _client = aioredis.from_url(_REDIS_URL, decode_responses=True)
    return _client


async def enqueue_embed_job(
    *, message_log_id: str, chat_id: int, content_type: str
) -> None:
    """Push a vectorization job. Best-effort: logs and swallows on failure."""
    job = {
        "message_log_id": message_log_id,
        "chat_id": chat_id,
        "content_type": content_type,
    }
    try:
        await _redis().lpush(EMBED_QUEUE_KEY, json.dumps(job))
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.error("Failed to enqueue embed job %s: %s", job, exc)


async def dequeue_embed_job(timeout: int = 5) -> Optional[dict]:
    """
    Blocking pop (BRPOP) of one job. Returns None on timeout so the worker can
    poll its shutdown flag between waits.
    """
    result = await _redis().brpop(EMBED_QUEUE_KEY, timeout=timeout)
    if result is None:
        return None
    _key, raw = result
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Dropping malformed embed job: %r", raw)
        return None


async def dead_letter(job: dict, error: str) -> None:
    """Persist a permanently-failed job for later inspection / retry."""
    payload = {**job, "error": error}
    try:
        await _redis().lpush(EMBED_DEAD_LETTER_KEY, json.dumps(payload))
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to write dead-letter for %s: %s", job, exc)
