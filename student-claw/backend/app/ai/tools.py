"""
Agnes AI tool definitions + executors (blueprint §3.3).

Holds the four OpenAI-standard function schemas and the server-side handlers
that execute them. Security invariant (§8.1): the authoritative `chat_id` is
injected by the backend on every call; any `chat_id` the model emits in its
arguments is IGNORED and overwritten. This makes cross-project access via
prompt injection impossible.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.ai import pipeline, repository

logger = logging.getLogger("student_claw.ai.tools")


# ---------------------------------------------------------------------------
# Tool JSON schemas (verbatim per §3.3)
# ---------------------------------------------------------------------------
TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "upsert_deadline",
            "description": (
                "Extract and store a project deadline when a student explicitly "
                "mentions a due date or submission date in the conversation. Only "
                "call this when a date is unambiguously stated. Upsert behavior: if "
                "a deadline with the same title already exists for this chat_id, "
                "update its due_date."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "integer",
                        "description": "The Telegram group chat ID. This is always provided by the system context and must not be inferred from conversation.",
                    },
                    "task_title": {
                        "type": "string",
                        "description": "A concise, human-readable title for the deadline. Example: 'Final Report Submission'. Maximum 200 characters.",
                        "maxLength": 200,
                    },
                    "due_date": {
                        "type": "string",
                        "format": "date-time",
                        "description": "The deadline in ISO 8601 with timezone. If only a date is mentioned, default to 23:59:00 Singapore Time (UTC+8).",
                    },
                    "source_message_id": {
                        "type": "integer",
                        "description": "The Telegram message_id of the message that contained the deadline mention.",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Confidence that this is a genuine, explicitly stated deadline. Values below 0.7 should not trigger this tool.",
                    },
                },
                "required": ["chat_id", "task_title", "due_date", "source_message_id", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_task",
            "description": (
                "Create and assign a task to a specific group member. Only call when: "
                "(a) a member explicitly volunteers, (b) a member is explicitly assigned "
                "by another member, or (c) a member's demonstrated expertise makes them "
                "the unambiguous choice AND delegation was requested. Never assign "
                "tasks speculatively."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "integer", "description": "The Telegram group chat ID from system context."},
                    "telegram_username": {
                        "type": "string",
                        "description": "The Telegram username (without @) of the member receiving the task. Must be a member listed in the project context.",
                    },
                    "task_description": {
                        "type": "string",
                        "description": "A detailed, actionable description: what to do, relevant context, and completion criteria if discernible.",
                        "maxLength": 1000,
                    },
                    "task_title": {"type": "string", "description": "Short title for the task card. Maximum 200 characters.", "maxLength": 200},
                    "priority": {
                        "type": "integer",
                        "enum": [1, 2, 3],
                        "description": "1=High (deadline within 48h or explicitly urgent), 2=Medium (default), 3=Low.",
                    },
                    "related_deadline_title": {
                        "type": "string",
                        "description": "Optional: the task_title of an existing deadline this task contributes to.",
                        "nullable": True,
                    },
                    "delegation_rationale": {
                        "type": "string",
                        "description": "Brief explanation of why this person was selected. Stored for transparency.",
                    },
                },
                "required": ["chat_id", "telegram_username", "task_description", "task_title", "priority", "delegation_rationale"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_contribution_metric",
            "description": (
                "Score a member's contribution over an evaluation window. Only call "
                "when explicitly requested by a group member (e.g. '/rate @username'). "
                "Never call autonomously. Scoring must be evidence-based."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "integer", "description": "The Telegram group chat ID from system context."},
                    "telegram_username": {"type": "string", "description": "The Telegram username (without @) being evaluated."},
                    "score_value": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 10.0,
                        "description": "Contribution score 0.00-10.00 (one decimal). Calibrate against the group: equal distribution = 5.0 each.",
                    },
                    "score_reason": {
                        "type": "string",
                        "description": "Detailed, objective, evidence-based justification citing specific actions. Avoid subjective language.",
                        "maxLength": 2000,
                    },
                    "scoring_window_start": {"type": "string", "format": "date-time", "description": "Start of evaluation period (ISO 8601)."},
                    "scoring_window_end": {"type": "string", "format": "date-time", "description": "End of evaluation period (ISO 8601). Defaults to now."},
                    "evidence_message_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Telegram message_ids used as evidence (audit trail).",
                        "maxItems": 50,
                    },
                },
                "required": ["chat_id", "telegram_username", "score_value", "score_reason", "scoring_window_start", "scoring_window_end"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_project_context",
            "description": (
                "Semantically search the project's stored conversation history, "
                "documents and files to answer specific questions. Use before "
                "answering any question that requires recalling specific past "
                "information not present in the current context window."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "integer", "description": "Scopes the search to this project only. Never search across projects."},
                    "query": {
                        "type": "string",
                        "description": "Semantic search query. Rephrase the user's question for similarity search.",
                        "maxLength": 500,
                    },
                    "content_type_filter": {
                        "type": "string",
                        "enum": ["all", "text", "image", "document"],
                        "description": "Optionally restrict to a content type. Default 'all'.",
                        "default": "all",
                    },
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "description": "Number of results. Default 8.", "default": 8},
                },
                "required": ["chat_id", "query"],
                "additionalProperties": False,
            },
        },
    },
]


class ToolExecutionError(Exception):
    """Raised on a malformed tool-call signature."""


def _parse_dt(value: str) -> datetime:
    """Parse an ISO 8601 string into an aware datetime (assume UTC if naive)."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------
async def execute_tool(name: str, arguments: dict[str, Any], *, chat_id: int) -> str:
    """
    Execute a tool call and return a string suitable for a `role: "tool"`
    message. `chat_id` is authoritative and always overrides arguments.

    Raises ToolExecutionError for unknown tools or malformed required args.
    """
    args = dict(arguments or {})
    args["chat_id"] = chat_id  # security override (§8.1)

    try:
        if name == "search_project_context":
            results = await pipeline.semantic_search(
                chat_id=chat_id,
                query=args["query"],
                top_k=int(args.get("top_k", 8)),
                content_type_filter=args.get("content_type_filter", "all"),
            )
            return _format_search_results(results)

        if name == "upsert_deadline":
            res = await repository.upsert_deadline(
                chat_id=chat_id,
                task_title=args["task_title"],
                due_date=_parse_dt(args["due_date"]),
                confidence=float(args.get("confidence", 0.0)),
                source_message_id=args.get("source_message_id"),
            )
            return _format_write(res)

        if name == "delegate_task":
            res = await repository.delegate_task(
                chat_id=chat_id,
                telegram_username=args["telegram_username"],
                task_title=args["task_title"],
                task_description=args["task_description"],
                priority=int(args.get("priority", 2)),
                delegation_rationale=args["delegation_rationale"],
                related_deadline_title=args.get("related_deadline_title"),
            )
            return _format_write(res)

        if name == "log_contribution_metric":
            res = await repository.log_contribution_metric(
                chat_id=chat_id,
                telegram_username=args["telegram_username"],
                score_value=float(args["score_value"]),
                score_reason=args["score_reason"],
                scoring_window_start=_parse_dt(args["scoring_window_start"]),
                scoring_window_end=_parse_dt(args["scoring_window_end"]),
                evidence_message_ids=args.get("evidence_message_ids"),
            )
            return _format_write(res)

    except KeyError as exc:
        raise ToolExecutionError(f"Tool {name} missing required argument: {exc}") from exc
    except (ValueError, TypeError) as exc:
        raise ToolExecutionError(f"Tool {name} received a malformed argument: {exc}") from exc

    raise ToolExecutionError(f"Unknown tool: {name!r}")


def _format_write(res: repository.ToolWriteResult) -> str:
    return json.dumps({"ok": res.ok, "detail": res.detail, "id": res.entity_id})


def _format_search_results(results: list[pipeline.SearchResult]) -> str:
    if not results:
        return json.dumps({"results": [], "note": "No relevant project context found."})
    return json.dumps(
        {
            "results": [
                {
                    "rank": i + 1,
                    "snippet": r.text_snippet,
                    "sender": r.sender_username,
                    "when": r.received_at,
                    "source": r.source_filename,
                    "score": round(r.score, 4),
                }
                for i, r in enumerate(results)
            ]
        }
    )
