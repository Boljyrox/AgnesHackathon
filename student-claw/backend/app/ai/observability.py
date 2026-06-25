"""
AI observability — records every Agnes AI call into `ai_request_logs`.

Wraps chat / embedding / vision requests so the SUTD_Admin dashboard can show
exactly what was sent and returned. Logging is best-effort: a failure to write
a log never affects the actual AI call. Payloads are trimmed summaries.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional

from app.database.connection import session_scope
from app.database.models import AIRequestLog

logger = logging.getLogger("student_claw.ai.observability")

_MAX_TEXT = 2000  # cap stored summary lengths


def _clip(text: Optional[str], limit: int = _MAX_TEXT) -> Optional[str]:
    if text is None:
        return None
    return text if len(text) <= limit else text[:limit] + "…"


def _usage_dict(usage: Any) -> dict[str, Optional[int]]:
    if usage is None:
        return {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


async def record_ai_call(
    *,
    kind: str,
    model: str,
    status: str,
    chat_id: Optional[int] = None,
    project_id: Optional[str] = None,
    latency_ms: Optional[int] = None,
    request_summary: Optional[str] = None,
    response_summary: Optional[str] = None,
    request_payload: Optional[dict] = None,
    response_payload: Optional[dict] = None,
    error: Optional[str] = None,
    usage: Any = None,
) -> None:
    """Insert one audit row. Swallows all errors."""
    tokens = _usage_dict(usage)
    try:
        async with session_scope() as session:
            session.add(
                AIRequestLog(
                    chat_id=chat_id,
                    project_id=uuid.UUID(project_id) if project_id else None,
                    kind=kind,
                    model=model,
                    status=status,
                    latency_ms=latency_ms,
                    request_summary=_clip(request_summary),
                    response_summary=_clip(response_summary),
                    request_payload=request_payload or {},
                    response_payload=response_payload or {},
                    error=_clip(error),
                    **tokens,
                )
            )
    except Exception as exc:  # pragma: no cover - logging must never break flow
        logger.warning("Failed to record AI call (%s/%s): %s", kind, status, exc)


def _last_user_text(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            content = m.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):  # vision-style content blocks
                for block in content:
                    if block.get("type") == "text":
                        return block.get("text", "")
    return ""


# ---------------------------------------------------------------------------
# Wrappers
# ---------------------------------------------------------------------------
async def logged_chat(
    client: Any,
    *,
    model: str,
    messages: list[dict],
    kind: str = "chat",
    chat_id: Optional[int] = None,
    project_id: Optional[str] = None,
    **kwargs: Any,
):
    """Wrap client.chat.completions.create with audit logging."""
    start = time.monotonic()
    tool_names = [t["function"]["name"] for t in kwargs.get("tools", []) or []]
    req_payload = {
        "message_count": len(messages),
        "tools": tool_names,
        "tool_choice": kwargs.get("tool_choice"),
    }
    try:
        resp = await client.chat.completions.create(
            model=model, messages=messages, **kwargs
        )
    except Exception as exc:
        await record_ai_call(
            kind=kind, model=model, status="error", chat_id=chat_id, project_id=project_id,
            latency_ms=int((time.monotonic() - start) * 1000),
            request_summary=_last_user_text(messages), request_payload=req_payload,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise

    msg = resp.choices[0].message
    called = [tc.function.name for tc in (msg.tool_calls or [])]
    resp_summary = (msg.content or "").strip() or (f"[tool_calls: {', '.join(called)}]" if called else "")
    await record_ai_call(
        kind=kind, model=model, status="success", chat_id=chat_id, project_id=project_id,
        latency_ms=int((time.monotonic() - start) * 1000),
        request_summary=_last_user_text(messages), request_payload=req_payload,
        response_summary=resp_summary,
        response_payload={"finish_reason": resp.choices[0].finish_reason, "tool_calls": called},
        usage=getattr(resp, "usage", None),
    )
    return resp


async def logged_embeddings(
    client: Any,
    *,
    model: str,
    input: list[str],
    chat_id: Optional[int] = None,
):
    """Wrap client.embeddings.create with audit logging."""
    start = time.monotonic()
    try:
        resp = await client.embeddings.create(model=model, input=input)
    except Exception as exc:
        await record_ai_call(
            kind="embedding", model=model, status="error", chat_id=chat_id,
            latency_ms=int((time.monotonic() - start) * 1000),
            request_summary=f"{len(input)} chunk(s)",
            request_payload={"chunk_count": len(input)},
            error=f"{type(exc).__name__}: {exc}",
        )
        raise

    await record_ai_call(
        kind="embedding", model=model, status="success", chat_id=chat_id,
        latency_ms=int((time.monotonic() - start) * 1000),
        request_summary=f"{len(input)} chunk(s)",
        request_payload={"chunk_count": len(input)},
        response_summary=f"{len(resp.data)} vector(s)",
        usage=getattr(resp, "usage", None),
    )
    return resp
