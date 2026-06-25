"""
Student Claw — Telegram bot package (Module 2).

Public surface:

    from app.bot import build_application, run_polling
    from app.bot import start_webhook_application, stop_webhook_application
    from app.bot.webhook import router as telegram_router
"""

from app.bot.bot import (
    build_application,
    get_application,
    run_polling,
    start_webhook_application,
    stop_webhook_application,
)
from app.bot.keys import (
    derive_project_key,
    normalize_project_key,
    vector_namespace_for,
    verify_project_key,
)

__all__ = [
    "build_application",
    "get_application",
    "run_polling",
    "start_webhook_application",
    "stop_webhook_application",
    "derive_project_key",
    "normalize_project_key",
    "verify_project_key",
    "vector_namespace_for",
]
