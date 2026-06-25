"""
Web-layer settings (auth, crypto, Google OAuth) — blueprint §7.3.

Kept separate from app.ai.config / app.bot.config so the web API can be
configured independently. Lazy + cached; required secrets are validated on
first access.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

ACCESS_TOKEN_TTL_SECONDS = 15 * 60          # 15 minutes
REFRESH_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name!r} is not set (§7.3).")
    return value


@dataclass(frozen=True)
class WebSettings:
    jwt_secret: str
    jwt_refresh_secret: str
    encryption_key_raw: str
    google_client_id: str
    google_client_secret: str


@lru_cache(maxsize=1)
def get_web_settings() -> WebSettings:
    return WebSettings(
        jwt_secret=_require("JWT_SECRET"),
        jwt_refresh_secret=_require("JWT_REFRESH_SECRET"),
        encryption_key_raw=_require("ENCRYPTION_KEY"),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
    )


def get_admin_token() -> str:
    """Shared secret gating the SUTD_Admin diagnostic dashboard."""
    return os.getenv("ADMIN_API_TOKEN", "")
