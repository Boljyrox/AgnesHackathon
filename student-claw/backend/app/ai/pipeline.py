"""
Embedding ingestion pipeline & semantic search (blueprint §5.1, §5.2).

Responsibilities:
  * ensure_collection      — create per-project Qdrant collection on demand.
  * embed_texts            — batch (<=20) Agnes AI embedding calls.
  * vectorize_message      — full per-message ingestion: parse → chunk → embed →
                             upsert → mark is_vectorized.
  * semantic_search        — query a project collection (used by the agent tool).
  * run_worker             — async loop draining the Redis embed_queue.

The collection is created lazily here (the bot persisted vector_namespace at
project registration in Module 2; this is where the actual Qdrant collection
comes into existence).
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Optional

from qdrant_client import models as qmodels

from app.ai import parser, queue, repository, storage, vision
from app.ai.chunking import (
    Chunk,
    ChatMessage,
    chunk_chat_messages,
    chunk_image_text,
    chunk_pdf,
    chunk_pptx_slides,
)
from app.ai.clients import get_agnes_client, get_qdrant_client
from app.ai.observability import logged_embeddings
from app.ai.config import (
    EMBED_BATCH_SIZE,
    MIME_PPTX,
    collection_name,
    get_ai_settings,
)

logger = logging.getLogger("student_claw.ai.pipeline")

_SNIPPET_LEN = 200
_MAX_RETRIES = int(os.getenv("EMBED_MAX_RETRIES", "3"))

# Guard concurrent ensure_collection calls per collection.
_collection_locks: dict[str, asyncio.Lock] = {}


# ---------------------------------------------------------------------------
# Qdrant collection management
# ---------------------------------------------------------------------------
async def ensure_collection(chat_id: int) -> str:
    name = collection_name(chat_id)
    lock = _collection_locks.setdefault(name, asyncio.Lock())
    async with lock:
        client = get_qdrant_client()
        if await client.collection_exists(name):
            return name
        dim = get_ai_settings().embed_dim
        await client.create_collection(
            collection_name=name,
            vectors_config=qmodels.VectorParams(
                size=dim, distance=qmodels.Distance.COSINE
            ),
        )
        logger.info("Created Qdrant collection %s (dim=%d).", name, dim)
    return name


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------
async def embed_texts(
    texts: list[str], *, chat_id: Optional[int] = None
) -> list[list[float]]:
    """Embed texts in batches of <=20 via the Agnes AI /embeddings endpoint."""
    if not texts:
        return []
    client = get_agnes_client()
    model = get_ai_settings().embed_model
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        resp = await logged_embeddings(client, model=model, input=batch, chat_id=chat_id)
        # Preserve request order.
        ordered = sorted(resp.data, key=lambda d: d.index)
        vectors.extend(d.embedding for d in ordered)
    return vectors


# ---------------------------------------------------------------------------
# Vectorization (one message_log)
# ---------------------------------------------------------------------------
@dataclass
class _Prepared:
    chunks: list[Chunk]
    source_filename: Optional[str]


async def _resolve_text_and_chunks(
    msg: repository.MessageForVectorization,
) -> Optional[_Prepared]:
    """Produce chunks for a message, parsing files from MinIO as needed."""
    ctype = msg.content_type

    if ctype == "text":
        text = parser.normalize_text(msg.raw_text)
        if not text:
            return None
        # Live per-message ingestion: a single chat message → one chunk.
        # (Sliding-window conversational chunking is used by reindex_chat.)
        return _Prepared([Chunk(text, 0)], None)

    if ctype == "image":
        if not msg.file_storage_path:
            return None
        text = msg.extracted_text
        if not text:
            data = await storage.fetch_bytes(msg.file_storage_path)
            text = await _understand_image(
                data, msg.file_mime_type or "image/jpeg", chat_id=msg.chat_id
            )
            if text:
                await repository.save_extracted_text(msg.id, text)
        if not text:
            return None
        return _Prepared(chunk_image_text(text), _basename(msg.file_storage_path))

    if ctype == "document":
        if not msg.file_storage_path:
            return None
        data = await storage.fetch_bytes(msg.file_storage_path)
        parsed = await parser.parse_document(
            data, msg.file_mime_type, _basename(msg.file_storage_path)
        )
        is_pptx = (msg.file_mime_type or "").lower() == MIME_PPTX or parsed.modality == "pptx"

        # Scanned / image-only PDF: PyMuPDF found little text → fall back to vision.
        if not is_pptx and len(parsed.text) < 40:
            vision_text = await _understand_pdf_via_vision(data, chat_id=msg.chat_id)
            if vision_text:
                parsed.text = vision_text

        if not parsed.text:
            return None
        await repository.save_extracted_text(msg.id, parsed.text)
        chunks = chunk_pptx_slides(parsed.segments) if is_pptx else chunk_pdf(parsed.text)
        return _Prepared(chunks, _basename(msg.file_storage_path))

    # voice (no transcription yet) or unknown → skip.
    logger.info("Skipping vectorization for unsupported content_type=%s", ctype)
    return None


def _basename(path: Optional[str]) -> Optional[str]:
    return path.rsplit("/", 1)[-1] if path else None


async def _understand_image(data: bytes, mime: str, *, chat_id: Optional[int] = None) -> str:
    """Agnes vision (primary) with Tesseract OCR fallback."""
    try:
        text = await vision.describe_image(data, mime, chat_id=chat_id)
        if text:
            return parser.normalize_text(text)
    except vision.VisionError as exc:
        logger.warning("Vision failed, falling back to OCR: %s", exc)
    try:
        parsed = await parser.extract_text_from_image(data)
        return parsed.text
    except Exception as exc:  # pragma: no cover - OCR optional
        logger.warning("OCR fallback also failed: %s", exc)
        return ""


async def _understand_pdf_via_vision(
    data: bytes, max_pages: int = 5, *, chat_id: Optional[int] = None
) -> str:
    """Render image-only PDF pages and read each with the vision model."""
    try:
        pages = await parser.render_pdf_pages_to_images(data, max_pages=max_pages)
    except Exception as exc:
        logger.warning("PDF page render failed: %s", exc)
        return ""
    out: list[str] = []
    for i, png in enumerate(pages):
        try:
            text = await vision.describe_image(png, "image/png", chat_id=chat_id)
            if text:
                out.append(parser.normalize_text(text))
        except vision.VisionError as exc:
            logger.warning("Vision failed on PDF page %d: %s", i, exc)
    return "\n\n".join(out)


async def vectorize_message(message_log_id: str) -> int:
    """
    Full ingestion for one message_log. Returns the number of points upserted.
    Idempotent: already-vectorized or deleted messages are skipped.
    """
    msg = await repository.get_message_for_vectorization(message_log_id)
    if msg is None:
        logger.warning("vectorize_message: %s not found.", message_log_id)
        return 0
    if msg.is_vectorized or msg.deleted:
        logger.debug("vectorize_message: %s already done/deleted.", message_log_id)
        return 0

    prepared = await _resolve_text_and_chunks(msg)
    if prepared is None or not prepared.chunks:
        logger.info("vectorize_message: nothing to embed for %s.", message_log_id)
        return 0

    texts = [c.text for c in prepared.chunks]
    vectors = await embed_texts(texts, chat_id=msg.chat_id)
    if len(vectors) != len(texts):
        raise RuntimeError(
            f"Embedding count mismatch: {len(vectors)} vs {len(texts)} chunks."
        )

    name = await ensure_collection(msg.chat_id)
    point_ids: list[uuid.UUID] = []
    points: list[qmodels.PointStruct] = []
    received_iso = msg.received_at.isoformat()

    for chunk, vector in zip(prepared.chunks, vectors):
        pid = uuid.uuid4()
        point_ids.append(pid)
        points.append(
            qmodels.PointStruct(
                id=str(pid),
                vector=vector,
                payload={  # exact §2.4 point payload schema
                    "chat_id": msg.chat_id,
                    "project_id": msg.project_id,
                    "message_log_id": msg.id,
                    "content_type": msg.content_type,
                    "sender_username": msg.sender_username,
                    "received_at": received_iso,
                    "chunk_index": chunk.chunk_index,
                    "source_filename": prepared.source_filename,
                    "text_snippet": chunk.text[:_SNIPPET_LEN],
                },
            )
        )

    await get_qdrant_client().upsert(collection_name=name, points=points)
    await repository.mark_vectorized(msg.id, msg.project_id, point_ids)
    logger.info("Vectorized %s → %d points in %s.", message_log_id, len(points), name)
    return len(points)


# ---------------------------------------------------------------------------
# Bulk conversational re-index (sliding-window chat chunking, §2.4)
# ---------------------------------------------------------------------------
async def reindex_chat(chat_id: int) -> int:
    """
    Rebuild a conversational vector layer from the full message history using
    the 10-message / 2-overlap sliding window. Intended for backfill or
    re-indexing after a cache cleanse — distinct from the live per-message path
    (which embeds single messages). Returns the number of windows upserted.

    Each window is anchored to its last message_log_id for payload provenance.
    Per-message is_vectorized flags are NOT touched here; this adds a
    complementary conversational layer.
    """
    rows = await repository.load_chat_messages_for_reindex(chat_id)
    if not rows:
        return 0

    messages = [
        ChatMessage(message_log_id=r.message_log_id, sender=r.sender, text=r.text)
        for r in rows
    ]
    windows = chunk_chat_messages(messages)
    if not windows:
        return 0

    vectors = await embed_texts([w.text for w in windows], chat_id=chat_id)
    name = await ensure_collection(chat_id)
    points: list[qmodels.PointStruct] = []
    for window, vector in zip(windows, vectors):
        points.append(
            qmodels.PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "chat_id": chat_id,
                    "project_id": None,
                    "message_log_id": window.anchor_message_log_id,
                    "content_type": "text",
                    "sender_username": None,
                    "received_at": None,
                    "chunk_index": window.chunk_index,
                    "source_filename": None,
                    "text_snippet": window.text[:_SNIPPET_LEN],
                },
            )
        )
    await get_qdrant_client().upsert(collection_name=name, points=points)
    logger.info("Re-indexed chat %s → %d conversational windows.", chat_id, len(points))
    return len(points)


# ---------------------------------------------------------------------------
# Semantic search (agent tool: search_project_context)
# ---------------------------------------------------------------------------
@dataclass
class SearchResult:
    text_snippet: str
    score: float
    message_log_id: str
    sender_username: Optional[str]
    received_at: Optional[str]
    source_filename: Optional[str]
    content_type: Optional[str]


async def semantic_search(
    chat_id: int,
    query: str,
    top_k: int = 8,
    content_type_filter: str = "all",
) -> list[SearchResult]:
    """
    Embed the query and search ONLY this project's collection (§5.2).
    Results are deduplicated by message_log_id (highest score wins).
    """
    name = collection_name(chat_id)
    client = get_qdrant_client()
    if not await client.collection_exists(name):
        return []

    query_vec = (await embed_texts([query], chat_id=chat_id))[0]

    query_filter = None
    if content_type_filter and content_type_filter != "all":
        query_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="content_type",
                    match=qmodels.MatchValue(value=content_type_filter),
                )
            ]
        )

    hits = await client.search(
        collection_name=name,
        query_vector=query_vec,
        limit=max(top_k * 2, top_k),  # over-fetch to survive dedup
        query_filter=query_filter,
        with_payload=True,
    )

    best: dict[str, SearchResult] = {}
    for h in hits:
        payload = h.payload or {}
        mlid = str(payload.get("message_log_id", h.id))
        existing = best.get(mlid)
        if existing is None or h.score > existing.score:
            best[mlid] = SearchResult(
                text_snippet=payload.get("text_snippet", ""),
                score=float(h.score),
                message_log_id=mlid,
                sender_username=payload.get("sender_username"),
                received_at=payload.get("received_at"),
                source_filename=payload.get("source_filename"),
                content_type=payload.get("content_type"),
            )
    ranked = sorted(best.values(), key=lambda r: r.score, reverse=True)
    return ranked[:top_k]


# ---------------------------------------------------------------------------
# Cache cleansing (blueprint §5.3) — 8-step transactional procedure
# ---------------------------------------------------------------------------
@dataclass
class CleanseResult:
    ok: bool
    vectors_deleted: bool
    files_deleted: bool
    messages_soft_deleted: int
    status: str


async def clear_project_cache(project_id: str, *, include_files: bool) -> CleanseResult:
    """
    Execute the cache-cleanse for a project. The authorization check (lead role)
    is enforced by the calling endpoint; this performs steps 2-8.

    Qdrant and PostgreSQL are separate systems, so the steps are not one atomic
    transaction — each is made idempotent and partial failures are isolated:
      - vector delete fails  → abort, status reset to 'active'
      - MinIO delete fails   → vectors already gone; logged, continue
      - soft-delete fails    → retried by caller; idempotent
    """
    from sqlalchemy import func, update as _sql_update

    from app.database.models import MessageLog, Project

    pid = uuid.UUID(project_id)
    vectors_deleted = False
    files_deleted = False
    soft_deleted = 0

    # Step 2: LOCK PROJECT (halt ingestion — the worker checks status).
    async with session_scope() as session:
        project = await session.get(Project, pid)
        if project is None:
            raise ValueError(f"Project {project_id} not found.")
        chat_id = project.chat_id
        project.status = "clearing"  # type: ignore[assignment]

    name = collection_name(chat_id)

    # Step 3: DELETE VECTOR STORE (single atomic Qdrant call).
    try:
        client = get_qdrant_client()
        if await client.collection_exists(name):
            await client.delete_collection(collection_name=name)
        vectors_deleted = True
    except Exception as exc:
        logger.error("Cache cleanse: vector delete failed for %s: %s", name, exc)
        async with session_scope() as session:
            await session.execute(
                _sql_update(Project).where(Project.id == pid).values(status="active")
            )
        raise

    # Step 4: DELETE MINIO FILES (optional, configurable).
    if include_files:
        try:
            await storage.delete_bucket(chat_id)
            files_deleted = True
        except Exception as exc:  # non-fatal: vectors already cleared
            logger.error("Cache cleanse: MinIO bucket delete failed: %s", exc)

    # Step 5: SOFT-DELETE MESSAGE LOGS (optimized single UPDATE).
    async with session_scope() as session:
        result = await session.execute(
            _sql_update(MessageLog)
            .where(MessageLog.project_id == pid, MessageLog.deleted_at.is_(None))
            .values(
                deleted_at=func.now(),
                is_vectorized=False,
                qdrant_point_ids=[],
            )
        )
        soft_deleted = result.rowcount or 0

    # Step 6: RESET PROJECT STATUS (steps 7-8: relational data untouched).
    async with session_scope() as session:
        await session.execute(
            _sql_update(Project)
            .where(Project.id == pid)
            .values(status="archived", qdrant_point_count=0, cleared_at=func.now())
        )

    logger.info(
        "Cache cleansed project %s: vectors=%s files=%s msgs=%d",
        project_id, vectors_deleted, files_deleted, soft_deleted,
    )
    return CleanseResult(
        ok=True,
        vectors_deleted=vectors_deleted,
        files_deleted=files_deleted,
        messages_soft_deleted=soft_deleted,
        status="archived",
    )


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------
async def _process_job(job: dict) -> None:
    message_log_id = job.get("message_log_id")
    if not message_log_id:
        logger.error("Malformed job (no message_log_id): %s", job)
        return

    last_exc: Optional[Exception] = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            await vectorize_message(message_log_id)
            return
        except parser.ParseError as exc:
            # Non-retryable: malformed/unsupported file. Dead-letter immediately.
            logger.error("Parse error for %s: %s", message_log_id, exc)
            await queue.dead_letter(job, f"parse_error: {exc}")
            return
        except Exception as exc:  # transient (network, embeddings, qdrant)
            last_exc = exc
            backoff = 2 ** (attempt - 1)
            logger.warning(
                "Embed attempt %d/%d failed for %s: %s (retry in %ss)",
                attempt, _MAX_RETRIES, message_log_id, exc, backoff,
            )
            await asyncio.sleep(backoff)

    logger.error("Giving up on %s after %d attempts.", message_log_id, _MAX_RETRIES)
    await queue.dead_letter(job, f"max_retries_exceeded: {last_exc}")


async def run_worker(stop_event: Optional[asyncio.Event] = None) -> None:
    """
    Drain the Redis embed_queue until `stop_event` is set (or forever).
    Run as a standalone process: `python -m app.ai.pipeline`.
    """
    logger.info("Embedding worker started.")
    stop_event = stop_event or asyncio.Event()
    while not stop_event.is_set():
        job = await queue.dequeue_embed_job(timeout=5)
        if job is None:
            continue
        try:
            await _process_job(job)
        except Exception as exc:  # pragma: no cover - last-resort guard
            logger.exception("Unhandled error processing job %s: %s", job, exc)
    logger.info("Embedding worker stopped.")


def _main() -> None:
    import logging as _logging

    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    _main()
