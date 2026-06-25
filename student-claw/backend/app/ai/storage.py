"""
MinIO (S3-compatible) object storage helper (blueprint §1.2, §5.1).

Files are partitioned into one bucket per chat: `chat-{chat_id}`. Because
Telegram group chat_ids are negative, the raw id is sanitised into a
DNS-compatible bucket name (negatives become an `n` prefix).

The `minio` SDK is synchronous; calls are off-loaded to threads via
asyncio.to_thread so the event loop is never blocked. This module deliberately
imports nothing heavier than `minio`, so the bot process can stream uploads
without pulling in the OCR / embedding stack.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
from functools import lru_cache

from minio import Minio
from minio.error import S3Error

from app.ai.config import get_minio_settings

logger = logging.getLogger("student_claw.ai.storage")


@lru_cache(maxsize=1)
def _client() -> Minio:
    s = get_minio_settings()
    return Minio(
        s.endpoint,
        access_key=s.access_key,
        secret_key=s.secret_key,
        secure=s.secure,
    )


def bucket_for_chat(chat_id: int) -> str:
    """DNS-safe bucket name for a chat: chat-<n?><abs(chat_id)>."""
    sign = "n" if chat_id < 0 else ""
    return f"chat-{sign}{abs(chat_id)}"


def storage_uri(chat_id: int, category: str, filename: str) -> str:
    """Canonical s3:// URI stored in message_logs.file_storage_path."""
    return f"s3://{bucket_for_chat(chat_id)}/{category}/{filename}"


def _ensure_bucket_sync(bucket: str) -> None:
    client = _client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def _put_sync(bucket: str, key: str, data: bytes, content_type: str) -> None:
    _ensure_bucket_sync(bucket)
    _client().put_object(
        bucket,
        key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type or "application/octet-stream",
    )


def _get_sync(bucket: str, key: str) -> bytes:
    resp = None
    try:
        resp = _client().get_object(bucket, key)
        return resp.read()
    finally:
        if resp is not None:
            resp.close()
            resp.release_conn()


def _parse_uri(uri: str) -> tuple[str, str]:
    """Split an s3://bucket/key URI into (bucket, key)."""
    if not uri.startswith("s3://"):
        raise ValueError(f"Not an s3 URI: {uri!r}")
    bucket, _, key = uri[len("s3://"):].partition("/")
    if not bucket or not key:
        raise ValueError(f"Malformed s3 URI: {uri!r}")
    return bucket, key


# ---------------------------------------------------------------------------
# Async public API
# ---------------------------------------------------------------------------
async def store_bytes(
    chat_id: int, category: str, filename: str, data: bytes, content_type: str
) -> str:
    """
    Store raw bytes under chat-{chat_id}/{category}/{filename} and return the
    canonical s3:// URI. `category` is e.g. "docs", "imgs", "voice".
    """
    bucket = bucket_for_chat(chat_id)
    key = f"{category}/{filename}"
    await asyncio.to_thread(_put_sync, bucket, key, data, content_type)
    uri = f"s3://{bucket}/{key}"
    logger.debug("Stored %d bytes -> %s", len(data), uri)
    return uri


async def fetch_bytes(uri: str) -> bytes:
    """Read an object back from its s3:// URI."""
    bucket, key = _parse_uri(uri)
    try:
        return await asyncio.to_thread(_get_sync, bucket, key)
    except S3Error as exc:
        logger.error("MinIO fetch failed for %s: %s", uri, exc)
        raise


async def delete_bucket(chat_id: int) -> None:
    """Delete an entire chat bucket (cache-cleanse, blueprint §5.3 Step 4)."""
    bucket = bucket_for_chat(chat_id)

    def _delete_all() -> None:
        client = _client()
        if not client.bucket_exists(bucket):
            return
        objects = client.list_objects(bucket, recursive=True)
        for obj in objects:
            client.remove_object(bucket, obj.object_name)
        client.remove_bucket(bucket)

    await asyncio.to_thread(_delete_all)
    logger.info("Deleted bucket %s", bucket)
