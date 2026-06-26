"""
Security primitives: password hashing, JWTs, and AES-256-GCM at-rest crypto.

Crypto contract (must match the Next.js BFF, frontend/src/lib/crypto.ts):
  ciphertext blob layout = IV(12 bytes) || ciphertext || GCM tag(16 bytes),
  base64-encoded. The IV is random per message and never reused; the
  authentication tag is appended (cryptography's AESGCM returns ciphertext||tag)
  so there is no separate tag field to leak or mishandle.
"""

from __future__ import annotations

import base64
import os
import time
import uuid
from typing import Any

import bcrypt
import jwt
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import (
    ACCESS_TOKEN_TTL_SECONDS,
    REFRESH_TOKEN_TTL_SECONDS,
    get_web_settings,
)

_ALGO = "HS256"
_IV_LEN = 12  # 96-bit nonce, the GCM-recommended size


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
def hash_password(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plaintext: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWTs
# ---------------------------------------------------------------------------
def create_access_token(
    *, student_id: str, username: str, telegram_verified: bool, project_ids: list[str]
) -> str:
    now = int(time.time())
    payload = {
        "sub": student_id,
        "username": username,
        "telegram_verified": telegram_verified,
        "project_ids": project_ids,
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, get_web_settings().jwt_secret, algorithm=_ALGO)


def create_refresh_token(*, student_id: str) -> str:
    now = int(time.time())
    payload = {
        "sub": student_id,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + REFRESH_TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, get_web_settings().jwt_refresh_secret, algorithm=_ALGO)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, get_web_settings().jwt_secret, algorithms=[_ALGO])


def decode_refresh_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, get_web_settings().jwt_refresh_secret, algorithms=[_ALGO])
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("Not a refresh token.")
    return payload


# ---------------------------------------------------------------------------
# AES-256-GCM
# ---------------------------------------------------------------------------
def _encryption_key() -> bytes:
    """Resolve a 32-byte key from hex (64 chars) or base64 ENCRYPTION_KEY."""
    raw = get_web_settings().encryption_key_raw
    try:
        if len(raw) == 64:
            key = bytes.fromhex(raw)
        else:
            key = base64.b64decode(raw)
    except Exception as exc:  # pragma: no cover - config error
        raise RuntimeError("ENCRYPTION_KEY is not valid hex or base64.") from exc
    if len(key) != 32:
        raise RuntimeError("ENCRYPTION_KEY must decode to exactly 32 bytes (AES-256).")
    return key


def encrypt_secret(plaintext: str) -> str:
    """Encrypt → base64(IV || ciphertext || tag)."""
    iv = os.urandom(_IV_LEN)
    ct = AESGCM(_encryption_key()).encrypt(iv, plaintext.encode("utf-8"), None)
    return base64.b64encode(iv + ct).decode("ascii")


def decrypt_secret(blob: str) -> str:
    """Decrypt a base64(IV || ciphertext || tag) blob produced by either stack."""
    raw = base64.b64decode(blob)
    if len(raw) < _IV_LEN + 16:
        raise ValueError("Ciphertext blob too short.")
    iv, ct = raw[:_IV_LEN], raw[_IV_LEN:]
    try:
        return AESGCM(_encryption_key()).decrypt(iv, ct, None).decode("utf-8")
    except InvalidTag as exc:
        raise ValueError("Authentication tag verification failed.") from exc
