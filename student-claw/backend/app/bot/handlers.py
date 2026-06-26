"""
Telegram update handlers for Student Claw (Module 2).

Implements:
  * /start, /help                         — basic commands
  * bot-added-to-group detection          — my_chat_member + new_chat_members
  * /verify {token}                        — Phase 4 identity verification
  * passive text/image/document listener   — RAG ingestion foundation

Handlers are deliberately thin: all DB work is delegated to app.bot.services,
each call being its own transaction. Domain events are emitted best-effort via
app.bot.events for the web dashboard's real-time sync.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import random
import re

from telegram import (
    Chat,
    ChatMemberUpdated,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatType
from telegram.ext import (
    ApplicationHandlerStop,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from app.ai import pipeline, queue, storage
from app.ai.agent import run_agent
from app.bot import events, modes, services
from app.bot.config import MAX_FILE_SIZE_BYTES
from app.database.models import ContentType, ProjectStatus

logger = logging.getLogger("student_claw.bot.handlers")


# ---------------------------------------------------------------------------
# Message copy
# ---------------------------------------------------------------------------
PRIVACY_NOTICE = (
    "ℹ️ Student Claw stores this group's messages to power task tracking, "
    "deadline extraction and project Q&A. A project lead can clear stored "
    "context anytime with /clearcache."
)


def _welcome_text(project_key: str, project_name: str) -> str:
    return (
        "✅ *Student Claw activated\\!*\n\n"
        f"*Project:* {_md(project_name)}\n"
        f"*Project Key:* `{project_key}`\n\n"
        "Share this key in the web dashboard to link your account, then send "
        "`/verify <token>` here to complete verification\\.\n\n"
        f"{_md(PRIVACY_NOTICE)}"
    )


def _md(text: str) -> str:
    """Escape text for Telegram MarkdownV2."""
    specials = r"_*[]()~`>#+-=|{}.!\\"
    return "".join(f"\\{c}" if c in specials else c for c in text)


# ---------------------------------------------------------------------------
# Basic commands
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        # Ensure the project exists (handles the case where the bot was added
        # before this handler shipped, or join events were missed).
        result = await services.get_or_create_project(chat.id, chat.title or "")
        await update.effective_message.reply_text(
            _welcome_text(result.project_key, result.name),
            parse_mode="MarkdownV2",
        )
    else:
        await update.effective_message.reply_text(
            "👋 Add me to your project group chat to get started. "
            "I'll give you a Project Key to link in the web dashboard."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Student Claw commands:\n"
        "/start — show this group's Project Key\n"
        "/verify <token> — link your web account (run inside the group)\n"
        "/ask <question> — ask Agnes anything about this project\n"
        "/summary — project status briefing\n"
        "/assign_work [focus] — delegate outstanding tasks to members\n"
        "/project_goals — state the project's goals\n"
        "/deadline [name] — list (and capture) deadlines\n"
        "/sync — ingest all shared files (OCR + index)\n"
        "/change_details — menu to edit goals, deadlines or tasks\n"
        "/setgoals <text> — set the project goals\n"
        "/status — set project status (upcoming/active/completed)\n"
        "/clear — wipe the project's vector memory\n"
        "/celebrate — end-of-project wrap-up 🎉\n"
        "/hehe — a joke to cheer the team up\n"
        "/deactivate — (admin) pause the bot in this group\n"
        "/activate — (admin) resume the bot\n"
        "/help — show this help"
    )


# ---------------------------------------------------------------------------
# Group join detection
# ---------------------------------------------------------------------------
def _was_bot_added(cmu: ChatMemberUpdated, bot_id: int) -> bool:
    """True when this my_chat_member update represents the bot being added."""
    if cmu.new_chat_member.user.id != bot_id:
        return False
    old_status = cmu.old_chat_member.status
    new_status = cmu.new_chat_member.status
    was_present = old_status in ("member", "administrator", "creator")
    is_present = new_status in ("member", "administrator", "creator")
    return is_present and not was_present


async def _register_and_welcome(chat: Chat, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Idempotently register a project for `chat` and post the welcome message."""
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    result = await services.get_or_create_project(chat.id, chat.title or "")
    if result.created:
        logger.info(
            "Registered new project %s for chat_id=%s (%s)",
            result.project_id, chat.id, result.name,
        )
        # New groups start uninitialised — scope their menu to just /init.
        await modes.apply_chat_commands(context.bot, chat.id, "uninitialized")
    try:
        await context.bot.send_message(
            chat_id=chat.id,
            text=_welcome_text(result.project_key, result.name),
            parse_mode="MarkdownV2",
        )
        if result.created:
            await context.bot.send_message(
                chat_id=chat.id,
                text="👉 Run /init to choose this group's mode and become its admin.",
            )
    except Exception as exc:  # pragma: no cover - network dependent
        logger.warning("Could not send welcome message to %s: %s", chat.id, exc)


async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Primary, reliable path: fires when the bot's own membership changes."""
    cmu = update.my_chat_member
    if cmu is None:
        return
    if _was_bot_added(cmu, context.bot.id):
        await _register_and_welcome(cmu.chat, context)


async def on_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Fallback path via the `new_chat_members` service message. Some client/server
    combinations surface this even when my_chat_member is also delivered; the
    underlying get_or_create_project call is idempotent so double-firing is safe.
    """
    msg = update.effective_message
    if not msg or not msg.new_chat_members:
        return
    if any(member.id == context.bot.id for member in msg.new_chat_members):
        await _register_and_welcome(update.effective_chat, context)


# ---------------------------------------------------------------------------
# /verify {token}
# ---------------------------------------------------------------------------
_VERIFY_ERRORS = {
    "invalid_token": "❌ That token is not valid. Generate a fresh one in the dashboard.",
    "consumed": "❌ That token has already been used. Generate a new one.",
    "expired": "❌ That token has expired (tokens last 15 minutes). Generate a new one.",
    "wrong_chat": "❌ That token was issued for a different group. Run /verify in the correct group.",
    "no_username": (
        "❌ Your Telegram account has no @username set. Add one in Telegram "
        "settings, then try again."
    ),
    "unknown_student": (
        "❌ No web account is registered with your Telegram username. Register "
        "on the dashboard first, making sure your Telegram username matches."
    ),
}


async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    sender = update.effective_user

    if chat is None or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await msg.reply_text("Run /verify inside your project group chat.")
        return

    if not context.args:
        await msg.reply_text("Usage: /verify <token>")
        return

    token = context.args[0].strip()

    result = await services.consume_link_token(
        token=token,
        chat_id=chat.id,
        telegram_user_id=sender.id,
        telegram_username=sender.username,
    )

    if not result.ok:
        await msg.reply_text(_VERIFY_ERRORS.get(result.reason, "❌ Verification failed."))
        return

    # Success — notify the dashboard in real time (best-effort).
    await events.publish_project_event(
        project_id=result.project_id,
        event_type="member_joined",
        payload={
            "student_id": result.student_id,
            "telegram_user_id": sender.id,
            "telegram_username": sender.username,
            "already_member": result.already_member,
        },
    )

    project_label = result.project_name or "your project"
    # Reply privately when possible to avoid leaking linkage in the group.
    confirmation = f"✅ Verified! Your account is now linked to {project_label}."
    try:
        await context.bot.send_message(chat_id=sender.id, text=confirmation)
        await msg.reply_text(f"✅ @{sender.username} is now verified.")
    except Exception:
        # Bot can't DM the user (they haven't started a private chat) — reply in group.
        await msg.reply_text(confirmation)


# ---------------------------------------------------------------------------
# Passive message listener (RAG foundation)
# ---------------------------------------------------------------------------
def _classify_content(update: Update) -> tuple[ContentType, str | None, str | None]:
    """
    Map a Telegram message to (content_type, raw_text, file_mime_type).

    File *download* and OCR/parse happen in Module 3; here we only capture
    metadata. Captions on media are preserved as raw_text.
    """
    msg = update.effective_message
    if msg.photo:
        return ContentType.image, msg.caption, None
    if msg.document:
        return ContentType.document, msg.caption, msg.document.mime_type
    if msg.voice:
        return ContentType.voice, msg.caption, msg.voice.mime_type
    # Plain text (and text-only edits).
    return ContentType.text, (msg.text or msg.caption), None


async def _download_and_store(
    update: Update, context: ContextTypes.DEFAULT_TYPE, content_type: ContentType
) -> tuple[str | None, str | None]:
    """
    Download a media message from Telegram and stream it into MinIO.

    Returns (file_storage_path, file_mime_type). Photos/documents are stored;
    oversized files and voice notes are skipped (voice has no transcription
    path yet — Module 3 only embeds text/image/document). Returns (None, None)
    when nothing was stored.
    """
    msg = update.effective_message
    chat = update.effective_chat

    if content_type == ContentType.image and msg.photo:
        tg_file = await msg.photo[-1].get_file()  # largest resolution
        category, mime = "imgs", "image/jpeg"
        filename = f"{tg_file.file_unique_id}.jpg"
    elif content_type == ContentType.document and msg.document:
        doc = msg.document
        if doc.file_size and doc.file_size > MAX_FILE_SIZE_BYTES:
            logger.info("Skipping oversized document (%s bytes).", doc.file_size)
            return None, doc.mime_type
        tg_file = await doc.get_file()
        category = "docs"
        mime = doc.mime_type
        filename = doc.file_name or tg_file.file_unique_id
    else:
        # Voice / unsupported — metadata only.
        return None, (msg.voice.mime_type if msg.voice else None)

    data = bytes(await tg_file.download_as_bytearray())
    if len(data) > MAX_FILE_SIZE_BYTES:
        logger.info("Skipping oversized download (%d bytes).", len(data))
        return None, mime

    storage_path = await storage.store_bytes(chat.id, category, filename, data, mime)
    return storage_path, mime


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Intercept all non-command text/image/document/voice messages in group chats,
    stream any media into MinIO, persist metadata to message_logs
    (is_vectorized=False), then enqueue an async embedding job.
    """
    chat = update.effective_chat
    msg = update.effective_message
    sender = update.effective_user

    if chat is None or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if msg is None:
        return

    # Consume a pending /sc free-text input (Set Goals / Set Details) — the user
    # replying to our ForceReply prompt. Not ingested into RAG.
    awaiting = context.chat_data.get("sc_await")
    if (
        awaiting
        and sender
        and awaiting.get("user_id") == sender.id
        and msg.reply_to_message
        and msg.reply_to_message.message_id == awaiting.get("prompt_id")
    ):
        context.chat_data.pop("sc_await", None)
        value = (msg.text or "").strip()
        if awaiting["action"] == "goals":
            ok = await services.update_project_goals(chat.id, value)
            await msg.reply_text("🎯 Project goals updated." if ok else "⚠️ Couldn't update goals.")
        elif awaiting["action"] == "goal_add":
            ok = await services.add_goal_line(chat.id, value)
            await msg.reply_text("🎯 Goal added." if ok else "⚠️ Couldn't add goal.")
        elif awaiting["action"] == "details":
            ok = await services.update_project_details(chat.id, value)
            await msg.reply_text("✏️ Project name updated." if ok else "⚠️ Couldn't update.")
        return

    content_type, raw_text, file_mime_type = _classify_content(update)

    # Expense-mode capture: parse "Ashok paid $15 for pizza" into the ledger.
    if raw_text and content_type == ContentType.text:
        m = _EXPENSE_RE.match(raw_text.strip())
        if m:
            state = await services.get_group_state(chat.id)
            if state and state.group_mode == "expense":
                payer = m.group(1).strip()
                amount = float(m.group(2))
                desc = (m.group(3) or "").strip()
                await services.add_expense(chat.id, payer, None, amount, desc or None)
                await msg.reply_text(
                    f"💸 Logged: <b>{payer}</b> paid {_money(amount)}"
                    + (f" for {desc}" if desc else ""),
                    parse_mode="HTML",
                )

    file_storage_path: str | None = None
    if content_type in (ContentType.image, ContentType.document):
        try:
            file_storage_path, file_mime_type = await _download_and_store(
                update, context, content_type
            )
        except Exception as exc:  # storage/download failure must not drop the log
            logger.error("Failed to download/store media in chat %s: %s", chat.id, exc)

    received_at = msg.date or datetime.now(timezone.utc)

    log_id = await services.log_incoming_message(
        chat_id=chat.id,
        telegram_message_id=msg.message_id,
        content_type=content_type,
        sender_telegram_user_id=sender.id if sender else None,
        sender_telegram_username=sender.username if sender else None,
        received_at=received_at,
        raw_text=raw_text,
        file_mime_type=file_mime_type,
        file_storage_path=file_storage_path,
    )

    if log_id is None:
        logger.debug("Message in unregistered chat_id=%s ignored.", chat.id)
        return

    # Enqueue async vectorization for content we can embed.
    if content_type in (ContentType.text, ContentType.image, ContentType.document):
        # Text needs actual content; media needs a stored file.
        has_payload = bool(raw_text) if content_type == ContentType.text else bool(file_storage_path)
        if has_payload:
            await queue.enqueue_embed_job(
                message_log_id=log_id,
                chat_id=chat.id,
                content_type=content_type.value,
            )

    logger.debug(
        "Logged message_log=%s chat_id=%s type=%s (enqueued for embedding)",
        log_id, chat.id, content_type.value,
    )


# ---------------------------------------------------------------------------
# /ask — invoke the Agnes agent (deferred "Thinking…" pattern, Requirement 2)
# ---------------------------------------------------------------------------
async def _deferred_agent(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    user_message: str,
    system_directive: str | None = None,
) -> None:
    """
    Reply with an immediate "🤔 Thinking…" placeholder, run the agent in a
    background task (so the webhook returns within Telegram's 10s window), then
    edit the placeholder with the final answer. The agent itself handles the
    OpenRouter/Gemini fallback (Requirement 2).
    """
    chat = update.effective_chat
    msg = update.effective_message
    sender = update.effective_user
    assert chat is not None and msg is not None

    placeholder = await msg.reply_text("🤔 Thinking…")

    async def _work() -> None:
        try:
            answer = await run_agent(chat.id, user_message, system_directive=system_directive)
        except Exception as exc:  # run_agent already guards; defend anyway
            logger.exception("Agent crashed in deferred task: %s", exc)
            answer = "⚠️ Something went wrong. Please try again."

        try:
            await context.bot.edit_message_text(
                chat_id=chat.id, message_id=placeholder.message_id,
                text=answer, parse_mode="HTML",
            )
        except Exception as exc:
            # Most likely a Telegram HTML-parse rejection — retry as plain text.
            logger.warning("edit_message_text (HTML) failed: %s", exc)
            try:
                await context.bot.edit_message_text(
                    chat_id=chat.id, message_id=placeholder.message_id,
                    text=services._strip_html(answer) or "(no response)",
                )
            except Exception as exc2:
                logger.error("edit_message_text (plain) failed: %s", exc2)

        # Persist the Q&A turn so the agent remembers it next time.
        try:
            await services.log_agent_interaction(
                chat_id=chat.id,
                asker_username=sender.username if sender else None,
                asker_user_id=sender.id if sender else None,
                question=user_message,
                answer=answer,
                q_message_id=msg.message_id,
                a_message_id=placeholder.message_id,
            )
        except Exception as exc:
            logger.warning("Failed to log agent interaction: %s", exc)

    context.application.create_task(_work(), update=update)


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run the bounded agentic loop on the user's question (deferred reply)."""
    chat = update.effective_chat
    msg = update.effective_message

    if chat is None or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await msg.reply_text("Ask me inside your project group chat.")
        return

    question = " ".join(context.args).strip() if context.args else ""
    if not question:
        await msg.reply_text("Usage: /ask <your question about the project>")
        return

    await _deferred_agent(update, context, user_message=question)


# ---------------------------------------------------------------------------
# Structured agent commands (each carries its own Agnes directive)
# ---------------------------------------------------------------------------
_SUMMARY_DIRECTIVE = (
    "The user invoked /summary. Produce a concise project status briefing using "
    "short bold headings: (1) Recent activity & decisions, (2) Outstanding tasks "
    "and who owns them, (3) Upcoming deadlines. Base everything strictly on the "
    "conversation, member roster, and stored context — call search_project_context "
    "for older details if needed. Never invent. Keep it scannable."
)
_ASSIGN_WORK_DIRECTIVE = (
    "The user invoked /assign_work. Identify concrete outstanding tasks from the "
    "conversation and delegate each to the most suitable member using the "
    "delegate_task tool. Choose assignees only from the real roster, based on who "
    "volunteered, who was assigned, or demonstrated expertise. Set sensible "
    "priorities and link an existing deadline when relevant. After delegating, "
    "reply with a short bulleted list of who got what and why. If there is nothing "
    "concrete to assign, say so rather than inventing work."
)
_PROJECT_GOALS_DIRECTIVE = (
    "The user invoked /project_goals. State this project's goals and objectives "
    "based on the conversation, module code, and any uploaded documents (use "
    "search_project_context if helpful). Give 3-6 concise goal bullets. If goals "
    "were never stated explicitly, infer the most likely objective from context "
    "and clearly label that section as 'Inferred'."
)
_DEADLINE_DIRECTIVE = (
    "The user invoked /deadline. List all known deadlines for this project sorted "
    "earliest first, each with its date and what it is for. If the recent "
    "conversation states a new, unambiguous deadline that isn't recorded yet, "
    "capture it with the upsert_deadline tool before replying. Never invent dates."
)


async def _run_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    directive: str,
    default_message: str,
) -> None:
    """Shared runner for the structured agent slash-commands."""
    chat = update.effective_chat
    msg = update.effective_message
    if chat is None or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await msg.reply_text("Run this inside your project group chat.")
        return

    # Any extra words after the command become additional focus for Agnes.
    extra = " ".join(context.args).strip() if context.args else ""
    user_message = f"{default_message} {extra}".strip() if extra else default_message

    await _deferred_agent(update, context, user_message=user_message, system_directive=directive)


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_command(
        update, context,
        directive=_SUMMARY_DIRECTIVE,
        default_message="Summarise the current state of this project.",
    )


async def assign_work_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_command(
        update, context,
        directive=_ASSIGN_WORK_DIRECTIVE,
        default_message="Assign the outstanding work for this project to the team.",
    )


async def project_goals_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_command(
        update, context,
        directive=_PROJECT_GOALS_DIRECTIVE,
        default_message="What are the goals and objectives of this project?",
    )


async def deadline_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_command(
        update, context,
        directive=_DEADLINE_DIRECTIVE,
        default_message="List all deadlines for this project.",
    )


# ---------------------------------------------------------------------------
# Activation state engine (Multi-Mode Group Agent)
# ---------------------------------------------------------------------------
async def state_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Global middleware (handler group -10, runs first). When a group's bot is
    deactivated, swallow ALL updates — text, file uploads, and commands — so the
    bot ignores everyone, EXCEPT an admin's /activate. Raises
    ApplicationHandlerStop to halt all further handler processing for the update.
    """
    chat = update.effective_chat
    if chat is None or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return  # DMs / channels pass through untouched

    state = await services.get_group_state(chat.id)
    if state is None or state.bot_active:
        return  # unregistered or active → normal processing

    # Deactivated: allow only an admin's /activate to wake it.
    msg = update.effective_message
    user = update.effective_user
    text = (msg.text or "") if msg else ""
    is_activate = text.split()[0].split("@")[0] == "/activate" if text else False
    if is_activate and services.can_admin(state, user.id if user else None):
        return  # let the /activate handler run

    raise ApplicationHandlerStop  # silently ignore everything else


async def activate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not _is_group(chat):
        await msg.reply_text("Use this inside your project group chat.")
        return
    state = await services.get_group_state(chat.id)
    if state is None:
        await msg.reply_text("⚠️ This group isn't registered yet. Send /start first.")
        return
    if not services.can_admin(state, update.effective_user.id if update.effective_user else None):
        await msg.reply_text("🔒 Only the group admin can activate the bot.")
        return
    await services.set_bot_active(chat.id, True)
    await msg.reply_text("✅ Student Claw is active again.")


async def deactivate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not _is_group(chat):
        await msg.reply_text("Use this inside your project group chat.")
        return
    state = await services.get_group_state(chat.id)
    if state is None:
        await msg.reply_text("⚠️ This group isn't registered yet. Send /start first.")
        return
    if not services.can_admin(state, update.effective_user.id if update.effective_user else None):
        await msg.reply_text("🔒 Only the group admin can deactivate the bot.")
        return
    await services.set_bot_active(chat.id, False)
    await msg.reply_text(
        "🔕 Student Claw is now <b>deactivated</b> and will ignore the group. "
        "An admin can wake me with /activate.",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Interactive commands & menus (Requirement 4)
# ---------------------------------------------------------------------------
_CELEBRATE_DIRECTIVE = (
    "The user invoked /celebrate — the project is complete. Write a warm, "
    "celebratory end-of-project wrap-up in Telegram HTML with emojis: "
    "congratulate the team, summarise what was accomplished (the completed "
    "tasks), gently acknowledge anything left undone, and thank everyone. Keep "
    "it upbeat and concise. Base it strictly on the task ledger provided."
)

_JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs. 🐛",
    "There are only 10 kinds of people: those who understand binary and those who don't.",
    "A SQL query walks into a bar, walks up to two tables and asks: 'Can I JOIN you?' 🍻",
    "I'd tell you a UDP joke, but you might not get it.",
    "Student life: 8 cups of coffee, 0 commits, infinite vibes. ☕",
    "Why was the function sad after the party? It didn't get called. 📞",
    "My code doesn't work, I have no idea why. My code works, I have no idea why. 🤷",
    "It's not a bug — it's an undocumented feature. ✨",
    "Deadlines are just suggestions delivered with anxiety. 🗓️",
    "Git commit -m 'final'. Git commit -m 'final FINAL'. Git commit -m 'final for real'. 😅",
]


def _is_group(chat: Chat | None) -> bool:
    return chat is not None and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


async def change_details_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_group(update.effective_chat):
        await update.effective_message.reply_text("Use this inside your project group chat.")
        return
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎯 Edit Goals", callback_data="cd:goals")],
            [InlineKeyboardButton("📅 Deadlines", callback_data="cd:deadlines")],
            [InlineKeyboardButton("✅ Assign Tasks", callback_data="cd:tasks")],
        ]
    )
    await update.effective_message.reply_text(
        "What would you like to change?", reply_markup=keyboard
    )


async def setgoals_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not _is_group(chat):
        await msg.reply_text("Use this inside your project group chat.")
        return
    goals = " ".join(context.args).strip() if context.args else ""
    if not goals:
        await msg.reply_text("Usage: /setgoals <your project goals>")
        return
    ok = await services.update_project_goals(chat.id, goals)
    await msg.reply_text(
        "🎯 Project goals updated." if ok else "⚠️ This group isn't registered yet."
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_group(update.effective_chat):
        await update.effective_message.reply_text("Use this inside your project group chat.")
        return
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🕒 Upcoming", callback_data="st:upcoming"),
                InlineKeyboardButton("⚡ Active", callback_data="st:active"),
                InlineKeyboardButton("✅ Completed", callback_data="st:completed"),
            ]
        ]
    )
    await update.effective_message.reply_text(
        "Set the project status:", reply_markup=keyboard
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_group(update.effective_chat):
        await update.effective_message.reply_text("Use this inside your project group chat.")
        return
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🗑️ Yes, clear", callback_data="clr:yes"),
                InlineKeyboardButton("Cancel", callback_data="clr:no"),
            ]
        ]
    )
    await update.effective_message.reply_text(
        "⚠️ Clear this project's vector memory? Files are kept, but Agnes's "
        "recall of past chat/documents is wiped. This can't be undone.",
        reply_markup=keyboard,
    )


async def celebrate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not _is_group(chat):
        await msg.reply_text("Use this inside your project group chat.")
        return

    ledger = await services.get_task_ledger(chat.id)
    if ledger is None:
        await msg.reply_text("⚠️ This group isn't registered yet.")
        return

    # Mark the project completed, then let Agnes write the celebration.
    await services.set_project_status(chat.id, ProjectStatus.completed)

    def _block(title: str, items: list[str]) -> str:
        body = "\n".join(f"- {t}" for t in items) or "(none)"
        return f"{title}:\n{body}"

    ledger_text = (
        _block("Completed", ledger["completed"])
        + "\n\n"
        + _block("Outstanding", ledger["outstanding"])
        + "\n\n"
        + _block("Dropped", ledger["dropped"])
    )
    user_message = (
        "The project is wrapping up. Here is the final task ledger:\n"
        f"{ledger_text}\n\nWrite the celebration message now."
    )
    await _deferred_agent(update, context, user_message=user_message, system_directive=_CELEBRATE_DIRECTIVE)


async def hehe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(random.choice(_JOKES))


async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Ensure every document/image/text shared in this chat is ingested into the
    backend (OCR + vectorise). Re-enqueues anything not yet vectorised.
    """
    chat = update.effective_chat
    msg = update.effective_message
    if not _is_group(chat):
        await msg.reply_text("Use this inside your project group chat.")
        return

    status = await msg.reply_text("🔄 Syncing shared files…")
    pending = await services.list_unvectorized_messages(chat.id)
    if pending is None:
        await status.edit_text("⚠️ This group isn't registered yet. Send /start first.")
        return
    if not pending:
        await status.edit_text("✅ Everything is already synced — nothing new to ingest.")
        return

    for message_log_id, content_type in pending:
        await queue.enqueue_embed_job(
            message_log_id=message_log_id, chat_id=chat.id, content_type=content_type
        )
    await status.edit_text(
        f"🔄 Queued <b>{len(pending)}</b> item(s) for OCR + indexing. "
        "Give it a minute, then ask me about them with /ask or in the web app.",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Inline-button callback router
# ---------------------------------------------------------------------------
_STATUS_LABELS = {
    "upcoming": "🕒 Upcoming",
    "active": "⚡ Active",
    "completed": "✅ Completed",
}


async def on_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    data = query.data or ""
    chat = update.effective_chat
    if chat is None:
        return

    # ---- /status ----
    if data.startswith("st:"):
        value = data.split(":", 1)[1]
        try:
            status = ProjectStatus(value)
        except ValueError:
            return
        ok = await services.set_project_status(chat.id, status)
        await query.edit_message_text(
            f"Project status set to <b>{_STATUS_LABELS.get(value, value)}</b>."
            if ok
            else "⚠️ This group isn't registered yet.",
            parse_mode="HTML",
        )
        return

    # ---- /clear ----
    if data.startswith("clr:"):
        if data == "clr:no":
            await query.edit_message_text("Cancelled — nothing was cleared.")
            return
        project_id = await services.resolve_project_id(chat.id)
        if project_id is None:
            await query.edit_message_text("⚠️ This group isn't registered yet.")
            return
        await query.edit_message_text("🧹 Clearing vector memory…")
        try:
            result = await pipeline.clear_project_cache(project_id, include_files=False)
            await query.edit_message_text(
                f"🧹 Vector memory cleared — {result.messages_soft_deleted} messages "
                "archived. Files were kept."
            )
        except Exception as exc:
            logger.error("clear cache failed: %s", exc)
            await query.edit_message_text("⚠️ Couldn't clear the cache. Please try again.")
        return

    # ---- /change_details ----
    if data.startswith("cd:"):
        action = data.split(":", 1)[1]
        if action == "goals":
            exists, goals = await services.get_project_goals(chat.id)
            if not exists:
                await query.edit_message_text("⚠️ This group isn't registered yet.")
                return
            current = goals or "(none set)"
            await query.edit_message_text(
                "🎯 To update the goals, send:\n"
                "<code>/setgoals your goals here</code>\n\n"
                f"<b>Current goals:</b>\n{_md_escape_min(current)}",
                parse_mode="HTML",
            )
        elif action == "deadlines":
            await query.edit_message_text("📅 Fetching deadlines…")
            await _deferred_agent(
                update, context,
                user_message="List all deadlines for this project.",
                system_directive=_DEADLINE_DIRECTIVE,
            )
        elif action == "tasks":
            await query.edit_message_text("✅ Reviewing work to assign…")
            await _deferred_agent(
                update, context,
                user_message="Assign the outstanding work for this project to the team.",
                system_directive=_ASSIGN_WORK_DIRECTIVE,
            )
        return


def _md_escape_min(text: str) -> str:
    """Minimal HTML escaping for user-provided goals shown in an HTML message."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# Multi-Mode: /init, mode selection, /admin_settings, Mode B & Mode C
# ---------------------------------------------------------------------------
_EXPENSE_RE = re.compile(
    r"^([A-Za-z][\w ]*?)\s+paid\s+\$?(\d+(?:\.\d{1,2})?)\s*(?:for\s+|on\s+|-\s*)?(.*)$",
    re.IGNORECASE,
)


def _mode_menu_keyboard() -> InlineKeyboardMarkup:
    rows = [[_btn(modes.MODE_LABELS[m], f"sc|mode|{m}")] for m in modes.MODE_ORDER]
    return InlineKeyboardMarkup(rows)


def _admin_settings_keyboard(allowed: dict) -> InlineKeyboardMarkup:
    def state(key: str) -> str:
        return "🟢 ON" if services.model_allowed(allowed, key) else "🔴 OFF"

    return InlineKeyboardMarkup(
        [
            [_btn(f"Qwen-VL (image/PDF OCR): {state('qwen_vl')}", "sc|am|qwen_vl")],
            [_btn(f"Gemini fallback: {state('gemini_fallback')}", "sc|am|gemini_fallback")],
            _back(),
        ]
    )


def _goals_editor_keyboard(lines: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for i, ln in enumerate(lines[:12]):
        label = (ln[:40] + "…") if len(ln) > 40 else ln
        rows.append([_btn(f"❌ {label}", f"sc|gedit|rm|{i}")])
    rows.append([_btn("➕ Add goal", "sc|gedit|add"), _btn("🗑 Clear", "sc|gedit|clear")])
    rows.append(_back("sc|set"))
    return InlineKeyboardMarkup(rows)


async def init_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """First-time initialisation: claim admin + choose the group's mode."""
    chat = update.effective_chat
    msg = update.effective_message
    if not _is_group(chat):
        await msg.reply_text("Run /init inside your group chat.")
        return
    state = await services.get_group_state(chat.id)
    if state is None:
        await msg.reply_text("⚠️ This group isn't registered yet. Send /start first.")
        return
    uid = update.effective_user.id if update.effective_user else None
    if state.group_admin_id is not None and state.group_admin_id != uid:
        await msg.reply_text("🔒 This group is already initialised. Only its admin can re-initialise.")
        return
    await msg.reply_text(
        "👋 <b>Welcome!</b> Pick what this group is for — you'll become its admin:",
        parse_mode="HTML",
        reply_markup=_mode_menu_keyboard(),
    )


async def admin_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not _is_group(chat):
        await msg.reply_text("Use this inside your group chat.")
        return
    state = await services.get_group_state(chat.id)
    if state is None:
        await msg.reply_text("⚠️ This group isn't registered yet.")
        return
    uid = update.effective_user.id if update.effective_user else None
    if not await services.is_privileged_user(chat.id, uid):
        await msg.reply_text("🔒 Leaders only.")
        return
    await msg.reply_text(
        "⚙️ <b>AI model settings</b> — tap to toggle:",
        parse_mode="HTML",
        reply_markup=_admin_settings_keyboard(state.allowed_models),
    )


# ── Mode B: Fun / Friend ──
async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(random.choice(_JOKES))


async def meme_prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not _is_group(chat):
        await update.effective_message.reply_text("Use this inside your group chat.")
        return
    await _deferred_agent(
        update, context,
        user_message="Suggest one funny, wholesome meme idea or caption for this friend group.",
        system_directive=(
            "Reply with a single short meme idea (format + caption) in a playful tone. "
            "Two lines max. Telegram HTML, emojis welcome."
        ),
    )


# ── Mode C: Expense Tracker ──
def _money(v: float) -> str:
    return f"${v:,.2f}"


async def add_expense_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    user = update.effective_user
    if not _is_group(chat):
        await msg.reply_text("Use this inside your group chat.")
        return
    if not context.args:
        await msg.reply_text("Usage: /add_expense <amount> <description>\ne.g. /add_expense 15 pizza")
        return
    try:
        amount = float(context.args[0].lstrip("$"))
    except ValueError:
        await msg.reply_text("First argument must be an amount, e.g. /add_expense 15 pizza")
        return
    desc = " ".join(context.args[1:]).strip()
    payer = (user.first_name if user else None) or (f"@{user.username}" if user and user.username else "Someone")
    ok = await services.add_expense(chat.id, payer, user.id if user else None, amount, desc or None)
    if not ok:
        await msg.reply_text("⚠️ This group isn't registered yet.")
        return
    await msg.reply_text(
        f"💸 Logged: <b>{payer}</b> paid {_money(amount)}" + (f" for {desc}" if desc else ""),
        parse_mode="HTML",
    )


async def list_expenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not _is_group(chat):
        await msg.reply_text("Use this inside your group chat.")
        return
    items = await services.list_expenses(chat.id, limit=20)
    if items is None:
        await msg.reply_text("⚠️ This group isn't registered yet.")
        return
    if not items:
        await msg.reply_text("No expenses logged yet. Add one with /add_expense 15 pizza")
        return
    total = sum(i["amount"] for i in items)
    lines = "\n".join(
        f"• <b>{i['payer']}</b> {_money(i['amount'])}" + (f" — {i['description']}" if i["description"] else "")
        for i in items
    )
    await msg.reply_text(
        f"💸 <b>Recent expenses</b> (total {_money(total)})\n{lines}", parse_mode="HTML"
    )


async def settle_up_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if not _is_group(chat):
        await msg.reply_text("Use this inside your group chat.")
        return
    result = await services.compute_balances(chat.id)
    if result is None:
        await msg.reply_text("⚠️ This group isn't registered yet.")
        return
    if result["count"] == 0:
        await msg.reply_text("No expenses to settle yet.")
        return
    bal_lines = "\n".join(
        f"• {name}: {'+' if net >= 0 else ''}{_money(net)}" for name, net in result["balances"]
    )
    if result["settlements"]:
        settle_lines = "\n".join(
            f"➡️ <b>{d}</b> pays <b>{c}</b> {_money(a)}" for d, c, a in result["settlements"]
        )
    else:
        settle_lines = "Everyone's square. 🎉"
    await msg.reply_text(
        f"🧾 <b>Settle up</b> (total {_money(result['total'])})\n\n"
        f"<b>Balances</b>\n{bal_lines}\n\n<b>Who pays whom</b>\n{settle_lines}",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Unified /sc inline menu + RBAC (app-like UX)
# ---------------------------------------------------------------------------
_SC_HEADER = "🤖 <b>Student Claw</b> — pick an option:"
_DENY = "🔒 Leaders only. Ask a group admin."

_SC_MENU_HELP = (
    "<b>Student Claw menu</b>\n\n"
    "Everything lives in /sc now:\n"
    "• <b>Summary / Assign Work / Project Goals / Deadlines</b> — Agnes helpers\n"
    "• <b>Sync</b> — index all shared files (OCR + vectors)\n"
    "• <b>Set</b> — goals, details, status, roles\n"
    "• <b>Clear / Activation</b> — leaders only\n"
    "• <b>Celebrate / Hehe</b> — for the vibes\n\n"
    "Outside the menu, just type <code>/ask &lt;question&gt;</code>."
)
_VERIFY_HELP = (
    "<b>Link your web account</b>\n"
    "1. Register on the dashboard with your Telegram @username.\n"
    "2. Submit your Project Key to get a token.\n"
    "3. Send <code>/verify &lt;token&gt;</code> here in the group."
)


def _btn(label: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=data)


def _back(to: str = "sc|main") -> list[InlineKeyboardButton]:
    return [_btn("🔙 Back", to)]


def _main_menu_keyboard(state: "services.GroupState", privileged: bool) -> InlineKeyboardMarkup:
    rows = [
        [_btn("✅ Verify", "sc|verify"), _btn("📋 Summary", "sc|summary")],
        [_btn("👥 Assign Work", "sc|assign"), _btn("🎯 Project Goals", "sc|goals")],
        [_btn("📅 Deadlines", "sc|deadlines"), _btn("🔄 Sync", "sc|sync")],
    ]
    set_row = [_btn("⚙️ Set", "sc|set")]
    if privileged:
        set_row.append(_btn("🗑️ Clear", "sc|clear"))
    rows.append(set_row)
    rows.append([_btn("🎉 Celebrate", "sc|celebrate"), _btn("😂 Hehe", "sc|hehe")])
    last: list[InlineKeyboardButton] = []
    if privileged:
        dot = "🟢" if state.bot_active else "🔴"
        last.append(_btn(f"{dot} Activation", "sc|act"))
    last.append(_btn("❓ Help", "sc|help"))
    rows.append(last)
    return InlineKeyboardMarkup(rows)


def _set_menu_keyboard(privileged: bool) -> InlineKeyboardMarkup:
    rows = [[_btn("🎯 Set Goals", "sc|set|goals"), _btn("📊 Set Status", "sc|set|status")]]
    if privileged:
        rows.append([_btn("✏️ Set Details", "sc|set|details"), _btn("👑 Set Roles", "sc|set|roles")])
        rows.append([_btn("🔀 Set Mode", "sc|mode"), _btn("⚙️ AI Settings", "sc|am")])
    rows.append(_back())
    return InlineKeyboardMarkup(rows)


def _activation_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [_btn("🟢 Activate", "sc|act|on"), _btn("🔴 Deactivate", "sc|act|off")],
            _back(),
        ]
    )


def _roles_keyboard(members: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for m in members:
        name = m["display_name"]
        sid = m["student_id"]
        if m["role"] == "lead":
            rows.append([_btn(f"👑 {name} (Leader) → Member", f"sc|role|{sid}|member")])
        else:
            rows.append([_btn(f"👤 {name} (Member) → Leader", f"sc|role|{sid}|lead")])
    if not rows:
        rows.append([_btn("(no verified members yet)", "sc|set|roles")])
    rows.append(_back("sc|set"))
    return InlineKeyboardMarkup(rows)


async def sc_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Master command — opens the interactive menu."""
    chat = update.effective_chat
    msg = update.effective_message
    if not _is_group(chat):
        await msg.reply_text("Open the menu inside your project group chat.")
        return
    state = await services.get_group_state(chat.id)
    if state is None:
        await msg.reply_text("⚠️ This group isn't registered yet. Send /start first.")
        return
    uid = update.effective_user.id if update.effective_user else None
    privileged = await services.is_privileged_user(chat.id, uid)
    await msg.reply_text(
        _SC_HEADER, parse_mode="HTML",
        reply_markup=_main_menu_keyboard(state, privileged),
    )


async def _prompt_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, prompt: str
) -> None:
    """Set a per-user awaiting flag + ForceReply for free-text input (Set Goals/Details)."""
    chat = update.effective_chat
    user = update.effective_user
    sent = await context.bot.send_message(
        chat_id=chat.id, text=prompt, parse_mode="HTML",
        reply_markup=ForceReply(selective=True),
    )
    context.chat_data["sc_await"] = {
        "action": action,
        "user_id": user.id if user else None,
        "prompt_id": sent.message_id,
    }


async def on_sc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Router for the /sc menu tree (callback_data prefixed `sc|`)."""
    query = update.callback_query
    chat = update.effective_chat
    user = update.effective_user
    if query is None or chat is None:
        if query:
            await query.answer()
        return

    parts = (query.data or "").split("|")  # ["sc", action, sub?, ...]
    action = parts[1] if len(parts) > 1 else ""
    sub = parts[2] if len(parts) > 2 else None

    state = await services.get_group_state(chat.id)
    if state is None:
        await query.answer("Group not registered.", show_alert=True)
        return
    uid = user.id if user else None
    privileged = await services.is_privileged_user(chat.id, uid)

    # RBAC: gate sensitive actions even if a stale button is clicked.
    denied = (
        (action in {"clear", "act", "role", "mode", "am"})
        or (action == "set" and sub in {"details", "roles"})
    )
    if denied and not privileged:
        await query.answer(_DENY, show_alert=True)
        return

    # ── Navigation ──
    if action == "main":
        await query.answer()
        await query.edit_message_text(
            _SC_HEADER, parse_mode="HTML",
            reply_markup=_main_menu_keyboard(state, privileged),
        )
        return
    if action == "set" and sub is None:
        await query.answer()
        await query.edit_message_text(
            "⚙️ <b>Settings</b>", parse_mode="HTML",
            reply_markup=_set_menu_keyboard(privileged),
        )
        return
    if action == "act" and sub is None:
        await query.answer()
        cur = "🟢 Active" if state.bot_active else "🔴 Inactive"
        await query.edit_message_text(
            f"Activation — currently <b>{cur}</b>", parse_mode="HTML",
            reply_markup=_activation_menu_keyboard(),
        )
        return

    # ── Info screens ──
    if action == "help":
        await query.answer()
        await query.edit_message_text(
            _SC_MENU_HELP, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([_back()]),
        )
        return
    if action == "verify":
        await query.answer()
        await query.edit_message_text(
            _VERIFY_HELP, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([_back()]),
        )
        return

    # ── Leaf actions reusing existing command logic (new message below the menu) ──
    if action == "summary":
        await query.answer("Summarising…"); await summary_command(update, context); return
    if action == "assign":
        await query.answer("Assigning…"); await assign_work_command(update, context); return
    if action == "goals":
        await query.answer(); await project_goals_command(update, context); return
    if action == "deadlines":
        await query.answer(); await deadline_command(update, context); return
    if action == "sync":
        await query.answer("Syncing…"); await sync_command(update, context); return
    if action == "celebrate":
        await query.answer("🎉"); await celebrate_command(update, context); return
    if action == "hehe":
        await query.answer("😂"); await hehe_command(update, context); return
    if action == "clear":
        await query.answer(); await clear_command(update, context); return  # renders clr: confirm

    # ── Activation submenu ──
    if action == "act" and sub == "on":
        await services.set_bot_active(chat.id, True)
        await query.answer("Activated ✅")
        await query.edit_message_text(
            "✅ Student Claw is <b>active</b>.", parse_mode="HTML",
            reply_markup=_activation_menu_keyboard(),
        )
        return
    if action == "act" and sub == "off":
        await services.set_bot_active(chat.id, False)
        await query.answer("Deactivated 🔕")
        await query.edit_message_text(
            "🔕 Student Claw is <b>deactivated</b>. Send /activate to wake me.",
            parse_mode="HTML",
        )
        return

    # ── Mode selection (claim admin + scope commands) ──
    if action == "mode" and sub is None:
        await query.answer()
        await query.edit_message_text(
            "🔀 <b>Choose a mode</b> for this group:", parse_mode="HTML",
            reply_markup=_mode_menu_keyboard(),
        )
        return
    if action == "mode" and sub:
        ok = await services.initialise_group(chat.id, uid or 0, sub)
        if ok:
            await modes.apply_chat_commands(context.bot, chat.id, sub)
        await query.answer("Mode set ✅" if ok else "Failed.", show_alert=not ok)
        label = modes.MODE_LABELS.get(sub, sub)
        await query.edit_message_text(
            f"✅ This group is now in <b>{label}</b> mode. The command menu has been updated.",
            parse_mode="HTML",
        )
        return

    # ── Admin settings (AI model toggles) ──
    if action == "am" and sub is None:
        await query.answer()
        await query.edit_message_text(
            "⚙️ <b>AI model settings</b> — tap to toggle:", parse_mode="HTML",
            reply_markup=_admin_settings_keyboard(state.allowed_models),
        )
        return
    if action == "am" and sub:
        models = await services.toggle_allowed_model(chat.id, sub)
        await query.answer("Updated ✅")
        await query.edit_message_text(
            "⚙️ <b>AI model settings</b> — tap to toggle:", parse_mode="HTML",
            reply_markup=_admin_settings_keyboard(models or {}),
        )
        return

    # ── Interactive goals editor (tree) ──
    if action == "gedit":
        if sub == "add":
            await query.answer()
            await _prompt_input(update, context, "goal_add", "➕ Reply to this with ONE goal to add:")
            return
        if sub == "clear":
            await services.clear_goals(chat.id)
            await query.answer("Cleared")
        elif sub == "rm" and len(parts) >= 4:
            await services.remove_goal_line(chat.id, int(parts[3]))
            await query.answer("Removed")
        else:
            await query.answer()
        lines = await services.get_goal_lines(chat.id) or []
        body = "🎯 <b>Project Goals</b>\n" + (
            "\n".join(f"• {ln}" for ln in lines) if lines else "<i>(no goals yet)</i>"
        )
        await query.edit_message_text(
            body, parse_mode="HTML", reply_markup=_goals_editor_keyboard(lines)
        )
        return

    # ── Set submenu ──
    if action == "set" and sub == "status":
        await query.answer(); await status_command(update, context); return  # renders st: keyboard
    if action == "set" and sub == "goals":
        # Open the interactive goals editor tree (Mode A update).
        await query.answer()
        lines = await services.get_goal_lines(chat.id) or []
        body = "🎯 <b>Project Goals</b>\n" + (
            "\n".join(f"• {ln}" for ln in lines) if lines else "<i>(no goals yet)</i>"
        )
        await query.edit_message_text(
            body, parse_mode="HTML", reply_markup=_goals_editor_keyboard(lines)
        )
        return
    if action == "set" and sub == "details":
        await query.answer()
        await _prompt_input(update, context, "details", "✏️ Reply to this with the new <b>project name</b>:")
        return
    if action == "set" and sub == "roles":
        await query.answer()
        members = await services.list_members(chat.id)
        await query.edit_message_text(
            "👑 <b>Set Roles</b> — tap to promote/demote:", parse_mode="HTML",
            reply_markup=_roles_keyboard(members),
        )
        return

    # ── Role toggle ──
    if action == "role" and len(parts) >= 4:
        ok = await services.set_member_role(chat.id, parts[2], parts[3])
        await query.answer("Updated ✅" if ok else "Couldn't update.", show_alert=not ok)
        members = await services.list_members(chat.id)
        await query.edit_message_text(
            "👑 <b>Set Roles</b> — tap to promote/demote:", parse_mode="HTML",
            reply_markup=_roles_keyboard(members),
        )
        return

    await query.answer()


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------
def register_handlers(application) -> None:
    """Attach all Module 2 handlers to a PTB Application, in priority order."""
    # State engine: runs before everything else and can swallow updates when the
    # bot is deactivated (Multi-Mode Group Agent).
    application.add_handler(TypeHandler(Update, state_gate), group=-10)

    # ── Commands ──
    # Only /sc and /ask are exposed to users (the rest moved into the /sc menu).
    application.add_handler(CommandHandler("sc", sc_command))
    application.add_handler(CommandHandler("ask", ask_command))
    # Hidden-but-functional (not shown in the command menu):
    #   /activate — wakes the bot when the menu is blocked (deactivated state)
    #   /verify   — token-based account linking (a button can't carry the token)
    #   /start    — group registration / welcome
    application.add_handler(CommandHandler("activate", activate_command))
    application.add_handler(CommandHandler("verify", verify_command))
    application.add_handler(CommandHandler("start", start_command))

    # Multi-Mode: onboarding + admin settings (admin-gated inside).
    application.add_handler(CommandHandler("init", init_command))
    application.add_handler(CommandHandler("admin_settings", admin_settings_command))
    # Mode B (Fun/Friend) commands.
    application.add_handler(CommandHandler("joke", joke_command))
    application.add_handler(CommandHandler("meme_prompt", meme_prompt_command))
    # Mode C (Expense Tracker) commands.
    application.add_handler(CommandHandler("add_expense", add_expense_command))
    application.add_handler(CommandHandler("list_expenses", list_expenses_command))
    application.add_handler(CommandHandler("settle_up", settle_up_command))

    # ── Callback routers ──
    # New /sc menu tree (callback_data prefixed `sc|`).
    application.add_handler(CallbackQueryHandler(on_sc_callback, pattern=r"^sc\|"))
    # Reused confirm/status/legacy sub-flows (colon-delimited prefixes).
    application.add_handler(
        CallbackQueryHandler(on_callback_query, pattern=r"^(st|clr|cd):")
    )

    # Bot membership changes (primary join-detection path).
    application.add_handler(
        ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER)
    )

    # new_chat_members service message (fallback join-detection path).
    application.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_chat_members)
    )

    # Passive content listener: text / photo / document / voice, excluding
    # commands and service messages. Lowest priority so commands win.
    content_filter = (
        (filters.TEXT & ~filters.COMMAND)
        | filters.PHOTO
        | filters.Document.ALL
        | filters.VOICE
    )
    application.add_handler(MessageHandler(content_filter, on_message))
