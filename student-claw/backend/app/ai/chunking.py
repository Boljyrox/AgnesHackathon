"""
Chunking strategies (blueprint §2.4).

  * Chat messages: sliding window of 10 messages, 2-message overlap.
  * PDF documents: 512-token chunks, 64-token overlap (recursive char splitter).
  * PPTX slides:   per-slide, atomic (no splitting, no overlap).
  * Image OCR:     256-token chunks, 32-token overlap.

Token counting uses tiktoken when available (cl100k_base) and falls back to a
~4-chars-per-token heuristic otherwise, so the module has no hard dependency on
tiktoken.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Sequence

from app.ai.config import (
    CHAT_WINDOW_MESSAGES,
    CHAT_WINDOW_OVERLAP,
    IMAGE_CHUNK_OVERLAP,
    IMAGE_CHUNK_TOKENS,
    PDF_CHUNK_OVERLAP,
    PDF_CHUNK_TOKENS,
)

logger = logging.getLogger("student_claw.ai.chunking")


@dataclass
class Chunk:
    text: str
    chunk_index: int


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _encoding():
    try:
        import tiktoken  # type: ignore

        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # pragma: no cover - optional dependency
        return None


def count_tokens(text: str) -> int:
    enc = _encoding()
    if enc is not None:
        return len(enc.encode(text))
    return max(1, (len(text) + 3) // 4)


def _hard_token_split(text: str, max_tokens: int) -> list[str]:
    """Split text that has no usable separators into fixed token windows."""
    enc = _encoding()
    if enc is not None:
        ids = enc.encode(text)
        return [
            enc.decode(ids[i : i + max_tokens])
            for i in range(0, len(ids), max_tokens)
        ]
    # Heuristic char window (~4 chars/token).
    size = max_tokens * 4
    return [text[i : i + size] for i in range(0, len(text), size)]


# ---------------------------------------------------------------------------
# Recursive character splitter (PDF / image)
# ---------------------------------------------------------------------------
class RecursiveCharacterTextSplitter:
    """LangChain-style recursive splitter targeting a token budget with overlap."""

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""]

    def __init__(
        self,
        max_tokens: int,
        overlap_tokens: int,
        separators: Optional[Sequence[str]] = None,
    ) -> None:
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.separators = list(separators or self.DEFAULT_SEPARATORS)

    def split_text(self, text: str) -> list[str]:
        text = text.strip()
        if not text:
            return []
        atoms = self._to_atoms(text, self.separators)
        return self._merge(atoms)

    def _to_atoms(self, text: str, separators: Sequence[str]) -> list[str]:
        if count_tokens(text) <= self.max_tokens:
            return [text] if text.strip() else []
        if not separators:
            return _hard_token_split(text, self.max_tokens)

        sep, rest = separators[0], separators[1:]
        if sep == "":
            return _hard_token_split(text, self.max_tokens)
        if sep not in text:
            return self._to_atoms(text, rest)

        atoms: list[str] = []
        for piece in text.split(sep):
            if not piece:
                continue
            # Re-attach the separator so reconstructed text reads naturally.
            piece = piece + sep
            if count_tokens(piece) <= self.max_tokens:
                atoms.append(piece)
            else:
                atoms.extend(self._to_atoms(piece, rest))
        return atoms

    def _merge(self, atoms: list[str]) -> list[str]:
        chunks: list[str] = []
        current: list[str] = []
        current_tokens = 0

        for atom in atoms:
            t = count_tokens(atom)
            if current and current_tokens + t > self.max_tokens:
                chunks.append("".join(current).strip())
                current, current_tokens = self._overlap_tail(current)
            current.append(atom)
            current_tokens += t

        if current:
            tail = "".join(current).strip()
            if tail:
                chunks.append(tail)
        return chunks

    def _overlap_tail(self, atoms: list[str]) -> tuple[list[str], int]:
        """Keep trailing atoms up to overlap_tokens to seed the next chunk."""
        if self.overlap_tokens <= 0:
            return [], 0
        tail: list[str] = []
        total = 0
        for atom in reversed(atoms):
            t = count_tokens(atom)
            if total + t > self.overlap_tokens and tail:
                break
            tail.insert(0, atom)
            total += t
        return tail, total


# ---------------------------------------------------------------------------
# Public per-modality entrypoints
# ---------------------------------------------------------------------------
def chunk_pdf(text: str) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter(PDF_CHUNK_TOKENS, PDF_CHUNK_OVERLAP)
    return [Chunk(t, i) for i, t in enumerate(splitter.split_text(text))]


def chunk_image_text(text: str) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter(IMAGE_CHUNK_TOKENS, IMAGE_CHUNK_OVERLAP)
    return [Chunk(t, i) for i, t in enumerate(splitter.split_text(text))]


def chunk_pptx_slides(slides: Sequence[str]) -> list[Chunk]:
    """One chunk per slide — slides are semantically atomic (§2.4)."""
    chunks: list[Chunk] = []
    idx = 0
    for slide in slides:
        s = slide.strip()
        if s:
            chunks.append(Chunk(s, idx))
            idx += 1
    return chunks


@dataclass
class ChatMessage:
    message_log_id: str
    sender: str
    text: str


@dataclass
class ChatChunk:
    text: str
    chunk_index: int
    anchor_message_log_id: str  # last message in the window


def chunk_chat_messages(
    messages: Sequence[ChatMessage],
    window: int = CHAT_WINDOW_MESSAGES,
    overlap: int = CHAT_WINDOW_OVERLAP,
) -> list[ChatChunk]:
    """
    Sliding window over an ordered list of chat messages (oldest→newest).

    Used for bulk/backfill conversational re-indexing (reindex_chat); the live
    per-message path embeds single messages to avoid re-embedding overlapping
    windows on every new message. Each window is anchored to its last
    message_log_id for payload provenance.
    """
    msgs = [m for m in messages if m.text and m.text.strip()]
    if not msgs:
        return []

    stride = max(1, window - overlap)
    chunks: list[ChatChunk] = []
    idx = 0
    for start in range(0, len(msgs), stride):
        window_msgs = msgs[start : start + window]
        if not window_msgs:
            break
        body = "\n".join(f"{m.sender}: {m.text}" for m in window_msgs)
        chunks.append(
            ChatChunk(
                text=body,
                chunk_index=idx,
                anchor_message_log_id=window_msgs[-1].message_log_id,
            )
        )
        idx += 1
        if start + window >= len(msgs):
            break
    return chunks
