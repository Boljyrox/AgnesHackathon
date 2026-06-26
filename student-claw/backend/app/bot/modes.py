"""
Multi-Mode definitions: per-mode command menus (for chat-scoped
set_my_commands) and AI personas injected into the agent's system prompt.
"""

from __future__ import annotations

import logging

from telegram import BotCommand, BotCommandScopeChat

logger = logging.getLogger("student_claw.bot.modes")

MODE_LABELS: dict[str, str] = {
    "projects": "📊 Projects",
    "fun": "😎 Fun / Friend",
    "expense": "💸 Expense Tracker",
    "event": "📅 Event Planner",
    "study": "📚 Study Buddy",
    "general": "💡 General Explainer",
}
MODE_ORDER = ["projects", "fun", "expense", "event", "study", "general"]

_COMMON = [
    BotCommand("sc", "Open the Student Claw menu"),
    BotCommand("ask", "Ask Agnes anything"),
]

# Commands shown in each chat's "/" menu (handlers stay globally registered).
MODE_COMMANDS: dict[str, list[BotCommand]] = {
    "uninitialized": [BotCommand("init", "Initialise this group")],
    "projects": _COMMON,
    "fun": _COMMON
    + [
        BotCommand("joke", "Get a joke"),
        BotCommand("meme_prompt", "Get a meme idea"),
    ],
    "expense": _COMMON
    + [
        BotCommand("add_expense", "Log an expense: /add_expense 15 pizza"),
        BotCommand("list_expenses", "List recent expenses"),
        BotCommand("settle_up", "Who owes whom"),
    ],
    "event": _COMMON,
    "study": _COMMON,
    "general": _COMMON,
}

# Persona prepended to the agent system prompt per mode.
PERSONA: dict[str, str] = {
    "projects": "",
    "fun": (
        "PERSONA: You're a witty, warm member of a close friend group. Be "
        "playful, casual and supportive — crack jokes, hype people up, use "
        "emojis, and keep the vibe light. Skip corporate/PM language entirely."
    ),
    "expense": (
        "PERSONA: You're the group's friendly, sharp treasurer. Help track "
        "shared expenses and who owes whom. Be concise and money-savvy; when "
        "amounts are mentioned, surface them clearly."
    ),
    "event": (
        "PERSONA: You're an upbeat event planner. Help the group coordinate "
        "dates, venues, tasks and logistics for outings and events."
    ),
    "study": (
        "PERSONA: You're a patient, encouraging study buddy. Explain concepts "
        "simply, quiz the group, and help them prep — supportive and clear."
    ),
    "general": (
        "PERSONA: You're a clear, friendly explainer. Answer questions about "
        "anything shared in the group in plain, well-structured language."
    ),
}


def persona_for(mode: str | None) -> str:
    return PERSONA.get(mode or "projects", "")


async def apply_chat_commands(bot, chat_id: int, mode: str) -> None:
    """Swap the visible command menu for a single chat (best-effort)."""
    commands = MODE_COMMANDS.get(mode, _COMMON)
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id))
        logger.info("Set chat-scoped commands for %s (mode=%s).", chat_id, mode)
    except Exception as exc:  # pragma: no cover - network dependent
        logger.warning("Could not set chat commands for %s: %s", chat_id, exc)
