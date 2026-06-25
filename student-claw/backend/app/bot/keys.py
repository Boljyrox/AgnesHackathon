"""
Key & namespace derivation utilities.

`project_key` is an HMAC-SHA256 over the canonical chat_id, truncated to the
first 16 hex characters (64 bits of entropy) and prefixed with "SC-". The raw
chat_id is never exposed; reversing the key requires the server-side HMAC
secret (blueprint §2.3, §8.1).
"""

from __future__ import annotations

import hashlib
import hmac

from app.bot.config import (
    PROJECT_KEY_PREFIX,
    VECTOR_NAMESPACE_TEMPLATE,
    get_hmac_secret,
)

_KEY_HEX_LEN = 16  # first 16 hex chars of the digest


def derive_project_key(chat_id: int, *, secret: str | None = None) -> str:
    """
    Deterministically derive the public project key for a Telegram chat_id.

    Returns e.g. "SC-4f8a2b9e1c3d7f0a". Deterministic: the same chat_id always
    yields the same key, which is what makes the web-dashboard linking flow work.
    """
    key = (secret or get_hmac_secret()).encode("utf-8")
    msg = str(chat_id).encode("utf-8")
    digest = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return f"{PROJECT_KEY_PREFIX}{digest[:_KEY_HEX_LEN]}"


def normalize_project_key(submitted: str) -> str:
    """
    Normalize a user-submitted key for lookup: trim whitespace, uppercase the
    prefix, and ensure the "SC-" prefix is present. The hex body is lowercased
    to match `derive_project_key` output.
    """
    s = submitted.strip()
    if s.upper().startswith(PROJECT_KEY_PREFIX):
        body = s[len(PROJECT_KEY_PREFIX):]
        return f"{PROJECT_KEY_PREFIX}{body.lower()}"
    # Accept a bare hex body too.
    return f"{PROJECT_KEY_PREFIX}{s.lower()}"


def verify_project_key(chat_id: int, submitted: str, *, secret: str | None = None) -> bool:
    """Constant-time check that `submitted` is the valid key for chat_id."""
    expected = derive_project_key(chat_id, secret=secret)
    return hmac.compare_digest(expected, normalize_project_key(submitted))


def vector_namespace_for(chat_id: int) -> str:
    """Qdrant collection name for a project: project_{chat_id}."""
    return VECTOR_NAMESPACE_TEMPLATE.format(chat_id=chat_id)
