"""
Student Claw — FastAPI application entrypoint.

Wires together the web API routers (auth, projects, tasks, deadlines, cache,
contributions, students) and the Telegram webhook, and manages process
lifecycle (bot startup/shutdown, DB pool + AI client teardown).

Run:  uvicorn main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    admin,
    auth,
    cache,
    contributions,
    deadlines,
    me,
    projects,
    students,
    tasks,
)

logger = logging.getLogger("student_claw.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        try:
            from app.bot.bot import start_webhook_application

            await start_webhook_application()
            logger.info("Telegram webhook application started.")
        except Exception as exc:  # pragma: no cover - env dependent
            logger.error("Failed to start Telegram bot: %s", exc)

    yield

    # --- shutdown ---
    try:
        from app.bot.bot import stop_webhook_application

        await stop_webhook_application()
    except Exception:  # pragma: no cover
        pass
    try:
        from app.ai.clients import close_clients

        await close_clients()
    except Exception:  # pragma: no cover
        pass
    from app.database.connection import dispose_engine

    await dispose_engine()


app = FastAPI(title="Student Claw API", version="1.0.0", lifespan=lifespan)

# The Next.js BFF calls server-side, but allow a configurable browser origin
# for local tooling / direct API exploration.
_origins = [o for o in os.getenv("CORS_ORIGINS", "").split(",") if o]
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Web API routers (mounted at root to match the BFF contract).
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(deadlines.router)
app.include_router(cache.router)
app.include_router(contributions.router)
app.include_router(students.router)
app.include_router(admin.router)

# Telegram webhook (Module 2). Imported lazily-safe at module load.
try:
    from app.bot.webhook import router as telegram_router

    app.include_router(telegram_router)
except Exception as exc:  # pragma: no cover - telegram optional in some envs
    logger.warning("Telegram webhook router not mounted: %s", exc)
