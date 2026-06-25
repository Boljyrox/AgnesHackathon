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

from telegram import Chat, ChatMemberUpdated, Update
from telegram.constants import ChatType
from telegram.ext import (
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.ai import queue, storage
from app.ai.agent import run_agent
from app.bot import events, services
from app.bot.config import MAX_FILE_SIZE_BYTES
from app.database.models import ContentType

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
        # NOTE: Qdrant collection creation for `result.vector_namespace`
        # happens in Module 3 (RAG/embedding layer). The vector_namespace is
        # already persisted here so the worker can create it lazily.
    try:
        await context.bot.send_message(
            chat_id=chat.id,
            text=_welcome_text(result.project_key, result.name),
            parse_mode="MarkdownV2",
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

    content_type, raw_text, file_mime_type = _classify_content(update)

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
# /ask — invoke the Agnes agent
# ---------------------------------------------------------------------------
async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run the bounded agentic loop on the user's question and reply in HTML."""
    chat = update.effective_chat
    msg = update.effective_message

    if chat is None or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await msg.reply_text("Ask me inside your project group chat.")
        return

    question = " ".join(context.args).strip() if context.args else ""
    if not question:
        await msg.reply_text("Usage: /ask <your question about the project>")
        return

    await context.bot.send_chat_action(chat_id=chat.id, action="typing")
    answer = await run_agent(chat.id, question)
    await msg.reply_text(answer or "🤔 I couldn't form a response.", parse_mode="HTML")


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

    await context.bot.send_chat_action(chat_id=chat.id, action="typing")
    answer = await run_agent(chat.id, user_message, system_directive=directive)
    await msg.reply_text(answer or "🤔 I couldn't form a response.", parse_mode="HTML")


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
# Handler registration
# ---------------------------------------------------------------------------
def register_handlers(application) -> None:
    """Attach all Module 2 handlers to a PTB Application, in priority order."""
    # Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("verify", verify_command))
    application.add_handler(CommandHandler("ask", ask_command))
    application.add_handler(CommandHandler("summary", summary_command))
    application.add_handler(CommandHandler("assign_work", assign_work_command))
    application.add_handler(CommandHandler("project_goals", project_goals_command))
    application.add_handler(CommandHandler("deadline", deadline_command))

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
