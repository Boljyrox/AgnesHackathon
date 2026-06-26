"""
Agnes AI vision — image & scanned-document understanding.

`agnes-2.0-flash` accepts OpenAI-style image inputs (an `image_url` content
block with a base64 `data:` URL). We use it to transcribe + describe images and
image-only PDF pages, which is far more capable than Tesseract OCR (it reads
diagrams, screenshots, handwriting, tables). Tesseract remains a local fallback
when the vision call fails.
"""

from __future__ import annotations

import base64
import logging

from app.ai.clients import get_agnes_client
from app.ai.config import get_ai_settings
from app.ai.observability import logged_chat

logger = logging.getLogger("student_claw.ai.vision")


class VisionError(Exception):
    """Raised when the vision model cannot process an image."""


_EXTRACTION_PROMPT = (
    "You are extracting content from an image shared in a student project group "
    "chat. Transcribe ALL visible text verbatim, preserving structure (lists, "
    "tables, headings). Then, in one short line, describe any diagrams, charts, "
    "screenshots, or handwriting. Output plain text only — no preamble, no "
    "markdown fences."
)


def _data_url(data: bytes, mime: str) -> str:
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime or 'image/jpeg'};base64,{b64}"


async def describe_image(
    data: bytes,
    mime: str = "image/jpeg",
    prompt: str | None = None,
    *,
    chat_id: int | None = None,
) -> str:
    """
    Send an image to the Agnes vision model and return the extracted text +
    description. Raises VisionError on failure so callers can fall back to OCR.
    """
    client = get_agnes_client()
    model = get_ai_settings().vision_model
    try:
        resp = await logged_chat(
            client,
            model=model,
            kind="vision",
            chat_id=chat_id,
            temperature=0.0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt or _EXTRACTION_PROMPT},
                        {"type": "image_url", "image_url": {"url": _data_url(data, mime)}},
                    ],
                }
            ],
        )
    except Exception as exc:
        raise VisionError(f"Vision request failed: {exc}") from exc

    text = (resp.choices[0].message.content or "").strip()
    logger.debug("Vision extracted %d chars from image (%d bytes).", len(text), len(data))
    return text
