"""
FastAPI router for receiving Telegram webhook updates (Module 2).

Mount this on the FastAPI app and drive the bot lifecycle from the app's
lifespan. Example (in backend/main.py):

    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from app.bot.bot import start_webhook_application, stop_webhook_application
    from app.bot.webhook import router as telegram_router

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await start_webhook_application()
        yield
        await stop_webhook_application()

    app = FastAPI(lifespan=lifespan)
    app.include_router(telegram_router)

Security: every request is authenticated against the
`X-Telegram-Bot-Api-Secret-Token` header, which Telegram echoes back from the
`secret_token` we registered with set_webhook (blueprint §8.1).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from telegram import Update

from app.bot.bot import get_application
from app.bot.config import get_settings

logger = logging.getLogger("student_claw.bot.webhook")

router = APIRouter(tags=["telegram"])


@router.post("/bot/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Response:
    """Receive a Telegram update, authenticate it, and dispatch to PTB."""
    settings = get_settings()

    # Constant-importance check: reject anything not signed with our secret.
    if x_telegram_bot_api_secret_token != settings.webhook_secret:
        logger.warning("Rejected webhook call with bad/missing secret token.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token"
        )

    application = get_application()

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON"
        )

    update = Update.de_json(data, application.bot)
    # process_update returns quickly; handlers run on the application loop.
    await application.process_update(update)

    # Telegram only needs a 200; an empty body acknowledges receipt.
    return Response(status_code=status.HTTP_200_OK)


@router.get("/bot/health")
async def bot_health() -> dict[str, str]:
    """Lightweight readiness probe for the bot subsystem."""
    return {"status": "ok"}
