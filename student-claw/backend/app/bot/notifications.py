"""
Bot-side notification listener (Requirement 3).

Subscribes to the Redis `bot_notifications` channel and forwards each message
into the target Telegram group. This decouples the FastAPI web app (which only
publishes) from the bot process (which holds the Telegram connection), so manual
web delegations can be announced in the group regardless of process topology.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

from telegram.ext import Application

from app.bot.events import BOT_NOTIFICATION_CHANNEL

logger = logging.getLogger("student_claw.bot.notifications")

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_task: asyncio.Task | None = None


async def _listen(application: Application) -> None:
    try:
        import redis.asyncio as aioredis  # type: ignore
    except Exception as exc:  # pragma: no cover
        logger.warning("redis not available; bot notifications disabled: %s", exc)
        return

    redis = aioredis.from_url(_REDIS_URL, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(BOT_NOTIFICATION_CHANNEL)
    logger.info("Subscribed to %s for group notifications.", BOT_NOTIFICATION_CHANNEL)

    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            try:
                data = json.loads(message["data"])
                chat_id = int(data["chat_id"])
                text = str(data["text"])
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning("Bad bot notification payload: %s", exc)
                continue
            try:
                await application.bot.send_message(
                    chat_id=chat_id, text=text, parse_mode="HTML"
                )
            except Exception as exc:  # pragma: no cover - network dependent
                logger.warning("Failed to deliver notification to %s: %s", chat_id, exc)
    except asyncio.CancelledError:  # graceful shutdown
        pass
    finally:
        try:
            await pubsub.unsubscribe(BOT_NOTIFICATION_CHANNEL)
            await redis.close()
        except Exception:  # pragma: no cover
            pass


def start_notification_listener(application: Application) -> None:
    """Launch the listener as a background task (idempotent)."""
    global _task
    if _task is not None and not _task.done():
        return
    _task = asyncio.create_task(_listen(application))
    logger.info("Bot notification listener started.")


async def stop_notification_listener() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
