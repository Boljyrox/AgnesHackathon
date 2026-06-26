"""
Lazily-constructed singleton clients for the AI subsystem.

  * Agnes AI  — OpenAI-compatible AsyncOpenAI client pointed at the Agnes hub.
  * Qdrant    — AsyncQdrantClient for vector storage / search.

Each is built once and reused across the FastAPI process and the embedding
worker. Heavy SDK imports happen here so lighter modules (queue, storage) stay
cheap to import.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from app.ai.config import get_ai_settings, get_qdrant_settings

logger = logging.getLogger("student_claw.ai.clients")


@lru_cache(maxsize=1)
def get_agnes_client() -> AsyncOpenAI:
    """OpenAI-compatible async client for Agnes AI (chat + embeddings)."""
    settings = get_ai_settings()
    logger.info("Initialising Agnes AI client (base_url=%s)", settings.agnes_base_url)
    return AsyncOpenAI(
        api_key=settings.agnes_api_key,
        base_url=settings.agnes_base_url,
        max_retries=3,
        timeout=60.0,
    )


@lru_cache(maxsize=1)
def get_openrouter_client() -> AsyncOpenAI | None:
    """
    OpenAI-compatible client for the OpenRouter fallback (Requirement 2).
    Returns None when OPENROUTER_API_KEY is not configured, so callers can skip
    the fallback gracefully.
    """
    settings = get_ai_settings()
    if not settings.openrouter_api_key:
        logger.info("OpenRouter not configured; fallback disabled.")
        return None
    logger.info("Initialising OpenRouter fallback client (model=%s).", settings.openrouter_model)
    return AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        max_retries=2,
        timeout=30.0,
    )


@lru_cache(maxsize=1)
def get_qdrant_client() -> AsyncQdrantClient:
    """Async Qdrant client."""
    settings = get_qdrant_settings()
    logger.info("Initialising Qdrant client (url=%s)", settings.url)
    return AsyncQdrantClient(url=settings.url, api_key=settings.api_key)


async def close_clients() -> None:
    """Close clients on graceful shutdown."""
    try:
        await get_qdrant_client().close()
    except Exception:  # pragma: no cover
        pass
    try:
        await get_agnes_client().close()
    except Exception:  # pragma: no cover
        pass
