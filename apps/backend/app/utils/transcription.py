import logging
import os
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def transcribe_audio(file_path: str, db: Optional[Session] = None) -> Dict:
    """
    Transcribe an audio file via OpenAI Speech-to-Text.

    Returns {"text": str, "language": str | None}.
    Raises on API error — callers must handle and mark content failed.
    """
    from app.services.ai_service import _resolve_openai_key
    from openai import OpenAI

    api_key = _resolve_openai_key(db)
    client = OpenAI(api_key=api_key, timeout=180.0)

    file_size_kb = os.path.getsize(file_path) / 1024
    logger.info(
        "Transcribing audio | size=%.1fKB model=%s",
        file_size_kb, settings.OPENAI_STT_MODEL,
    )

    with open(file_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            file=f,
            model=settings.OPENAI_STT_MODEL,
            response_format="verbose_json",
        )

    text = getattr(transcript, "text", "") or ""
    language = getattr(transcript, "language", None)

    logger.info(
        "Transcription complete | chars=%d language=%s",
        len(text), language,
    )
    return {"text": text, "language": language}
