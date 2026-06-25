"""
Multi-modal parsing & OCR (blueprint §5.1).

Pure extraction + normalisation. All heavy, blocking libraries (pytesseract,
PyMuPDF/fitz, python-pptx, Pillow) are invoked through asyncio.to_thread so the
event loop is never stalled. File download/storage lives in app.ai.storage; the
caller hands raw bytes to these extractors.

Returned `ParsedContent.segments` preserves natural boundaries (PDF pages /
PPTX slides) so the chunker can keep slides atomic while recursively splitting
PDFs.
"""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from app.ai.config import MIME_PDF, MIME_PPTX

logger = logging.getLogger("student_claw.ai.parser")


class ParseError(Exception):
    """Raised when a document cannot be parsed (malformed / unsupported)."""


@dataclass
class ParsedContent:
    text: str                       # full normalised text
    segments: list[str] = field(default_factory=list)  # page/slide boundaries
    modality: str = "text"          # "text" | "image" | "pdf" | "pptx"
    language: Optional[str] = None


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍﻿⁠"), None)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_WS_RE = re.compile(r"[ \t]{2,}")
_MULTI_NL_RE = re.compile(r"\n{3,}")
# Strip leftover Telegram/markdown entity noise that survives copy/paste.
_TG_MARKUP_RE = re.compile(r"(\*\*|__|~~|```|`)")


def normalize_text(text: Optional[str]) -> str:
    """
    Unicode-normalise (NFC), strip zero-width + control chars, remove broken
    Telegram markup, and collapse redundant whitespace. Idempotent.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.translate(_ZERO_WIDTH)
    text = _CONTROL_RE.sub("", text)
    text = _TG_MARKUP_RE.sub("", text)
    text = _MULTI_WS_RE.sub(" ", text)
    text = _MULTI_NL_RE.sub("\n\n", text)
    return text.strip()


def detect_language(text: str) -> Optional[str]:
    """Best-effort ISO-639-1 language detection; None if unavailable."""
    sample = text.strip()
    if len(sample) < 12:
        return None
    try:
        from langdetect import detect  # type: ignore

        return detect(sample)
    except Exception:  # pragma: no cover - optional dependency / short text
        return None


# ---------------------------------------------------------------------------
# Image OCR
# ---------------------------------------------------------------------------
def _ocr_image_sync(data: bytes) -> str:
    from io import BytesIO

    import pytesseract
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(BytesIO(data)) as img:
            img = img.convert("RGB")
            return pytesseract.image_to_string(img)
    except UnidentifiedImageError as exc:
        raise ParseError(f"Unrecognised image format: {exc}") from exc


async def extract_text_from_image(data: bytes) -> ParsedContent:
    raw = await asyncio.to_thread(_ocr_image_sync, data)
    text = normalize_text(raw)
    if not text:
        logger.info("OCR produced no text for image (%d bytes).", len(data))
    return ParsedContent(
        text=text,
        segments=[text] if text else [],
        modality="image",
        language=detect_language(text),
    )


# ---------------------------------------------------------------------------
# PDF (PyMuPDF / fitz)
# ---------------------------------------------------------------------------
def _pdf_pages_sync(data: bytes) -> list[str]:
    import fitz  # PyMuPDF

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ParseError(f"Could not open PDF: {exc}") from exc
    pages: list[str] = []
    try:
        for page in doc:
            try:
                pages.append(page.get_text("text") or "")
            except Exception as exc:  # pragma: no cover - per-page resilience
                logger.warning("Failed to extract a PDF page: %s", exc)
                pages.append("")
    finally:
        doc.close()
    return pages


def _pdf_pages_to_pngs_sync(data: bytes, max_pages: int, zoom: float = 2.0) -> list[bytes]:
    """Render the first `max_pages` PDF pages to PNG bytes (for vision fallback)."""
    import fitz  # PyMuPDF

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ParseError(f"Could not open PDF for rendering: {exc}") from exc
    images: list[bytes] = []
    try:
        matrix = fitz.Matrix(zoom, zoom)
        for page in doc[:max_pages]:
            pix = page.get_pixmap(matrix=matrix)
            images.append(pix.tobytes("png"))
    finally:
        doc.close()
    return images


async def render_pdf_pages_to_images(data: bytes, max_pages: int = 5) -> list[bytes]:
    """Async wrapper: render up to `max_pages` pages to PNG bytes."""
    return await asyncio.to_thread(_pdf_pages_to_pngs_sync, data, max_pages)


async def extract_text_from_pdf(data: bytes) -> ParsedContent:
    raw_pages = await asyncio.to_thread(_pdf_pages_sync, data)
    pages = [normalize_text(p) for p in raw_pages]
    pages = [p for p in pages if p]
    full = "\n\n".join(pages)
    if not full:
        logger.info("PDF contained no extractable text (%d bytes).", len(data))
    return ParsedContent(
        text=full, segments=pages, modality="pdf", language=detect_language(full)
    )


# ---------------------------------------------------------------------------
# PPTX (python-pptx) — slides are semantically atomic
# ---------------------------------------------------------------------------
def _pptx_slides_sync(data: bytes) -> list[str]:
    from io import BytesIO

    from pptx import Presentation

    try:
        prs = Presentation(BytesIO(data))
    except Exception as exc:
        raise ParseError(f"Could not open PPTX: {exc}") from exc

    slides: list[str] = []
    for slide in prs.slides:
        parts: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    line = "".join(run.text for run in para.runs)
                    if line:
                        parts.append(line)
            if shape.has_table:  # type: ignore[attr-defined]
                for row in shape.table.rows:
                    cells = [c.text for c in row.cells if c.text]
                    if cells:
                        parts.append(" | ".join(cells))
        slides.append("\n".join(parts))
    return slides


async def extract_text_from_pptx(data: bytes) -> ParsedContent:
    raw_slides = await asyncio.to_thread(_pptx_slides_sync, data)
    slides = [normalize_text(s) for s in raw_slides]
    slides = [s for s in slides if s]
    full = "\n\n".join(slides)
    return ParsedContent(
        text=full, segments=slides, modality="pptx", language=detect_language(full)
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
async def parse_document(data: bytes, mime_type: Optional[str], filename: str = "") -> ParsedContent:
    """
    Route a document to the right extractor by MIME type, with a filename-based
    fallback. Raises ParseError for unsupported types.
    """
    mime = (mime_type or "").lower()
    name = (filename or "").lower()

    if mime == MIME_PDF or name.endswith(".pdf"):
        return await extract_text_from_pdf(data)
    if mime == MIME_PPTX or name.endswith(".pptx"):
        return await extract_text_from_pptx(data)

    raise ParseError(f"Unsupported document type: mime={mime_type!r} name={filename!r}")
