"""
Bot configuration — environment-driven settings for the Telegram layer.

All secrets come from environment variables (blueprint §7.3). Importing this
module fails fast if a hard-required variable is missing in a context that
needs it, but key derivation / token secrets are validated lazily so that the
database-only test suite can import the package without a full bot env.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

# Public-facing project-key prefix shown to users, e.g. "SC-4f8a2b9e1c3d7f0a".
PROJECT_KEY_PREFIX = "SC-"

# Qdrant collection naming — blueprint §2.2 / §2.4: project_{chat_id}.
VECTOR_NAMESPACE_TEMPLATE = "project_{chat_id}"

# Hard limit enforced before we ever download a file (blueprint §8.1).
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


@dataclass(frozen=True)
class BotSettings:
    bot_token: str
    webhook_secret: str
    project_key_hmac_secret: str
    # Public base URL where Telegram will POST updates, e.g.
    # https://yourdomain.com  (the webhook path is appended).
    webhook_base_url: str
    webhook_path: str
    bot_username: str  # used to build deep links / mentions; optional

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_base_url.rstrip('/')}{self.webhook_path}"


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Required environment variable {name!r} is not set. "
            "See blueprint §7.3 for the full environment contract."
        )
    return value


@lru_cache(maxsize=1)
def get_settings() -> BotSettings:
    """Load and cache bot settings. Raises if required vars are absent."""
    return BotSettings(
        bot_token=_require("TELEGRAM_BOT_TOKEN"),
        webhook_secret=_require("TELEGRAM_WEBHOOK_SECRET"),
        project_key_hmac_secret=_require("PROJECT_KEY_HMAC_SECRET"),
        webhook_base_url=os.getenv("TELEGRAM_WEBHOOK_BASE_URL", ""),
        webhook_path=os.getenv("TELEGRAM_WEBHOOK_PATH", "/bot/webhook"),
        bot_username=os.getenv("TELEGRAM_BOT_USERNAME", "StudentClawBot"),
    )


def get_hmac_secret() -> str:
    """Fetch only the HMAC secret (used by key derivation without full settings)."""
    return _require("PROJECT_KEY_HMAC_SECRET")
