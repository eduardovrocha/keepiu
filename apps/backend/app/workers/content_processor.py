import asyncio
import os
import logging
import time
from uuid import UUID

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded
from sqlalchemy.orm import sessionmaker

from app.core.database import engine
from app.core.config import get_settings
from app.services.content_service import ContentService
from app.services.ai_service import AIService
from app.services.telegram_service import TelegramService
from app.utils.ocr import extract_text_from_image
from app.utils.link_extractor import extract_link_metadata_sync
from app.utils.audio import extract_audio
from app.utils.transcription import transcribe_audio
from app.services.metrics_service import save_task_metric
from app.workers.notifications import send_completion, send_failure

logger = logging.getLogger(__name__)
settings = get_settings()
SessionLocal = sessionmaker(bind=engine)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_content_task(self, content_id: str) -> None:
    """
    Process text/link content asynchronously:
    1. Mark as processing
    2. Extract link metadata (if applicable)
    3. Analyse with AI (title, summary, category, tags, importance)
    4. Generate and store embedding
    5. Mark as completed (or failed on exhausted retries)
    """
    db = SessionLocal()
    start = time.monotonic()
    logger.info("process_content_task started | content_id=%s attempt=%d", content_id, self.request.retries + 1)

    try:
        content_service = ContentService(db)
        ai_service = AIService(db=db)

        content = content_service.get_by_id(UUID(content_id))
        if not content:
            logger.warning("Content %s not found — skipping", content_id)
            return

        if content.processed:
            logger.info("Content %s already processed — skipping", content_id)
            return

        if content.type == "image":
            logger.warning(
                "Content %s is an image but routed to process_content_task — should use process_image_task",
                content_id,
            )
            return

        # ── Mark processing ────────────────────────────────────────────────
        content_service.mark_processing(UUID(content_id))

        # ── Link metadata extraction ───────────────────────────────────────
        extracted_text = None
        page_title = None
        page_description = None

        if content.type == "link" and content.url:
            content.processing_stage = "capturing"
            db.commit()
            logger.info("Extracting link metadata | content_id=%s url=%s", content_id, content.url)
            metadata = extract_link_metadata_sync(content.url)
            page_title = metadata.get("title")
            page_description = metadata.get("description")

        # ── AI analysis ────────────────────────────────────────────────────
        content.processing_stage = "ai_processing"
        db.commit()
        logger.info("Starting AI analysis | content_id=%s type=%s", content_id, content.type)
        analysis = ai_service.analyze_content(
            content_type=content.type,
            raw_text=content.raw_text,
            url=content.url,
            extracted_text=extracted_text,
            page_title=page_title,
            page_description=page_description,
        )

        # ── Persist results ────────────────────────────────────────────────
        # ── Embedding ──────────────────────────────────────────────────────
        content.processing_stage = "finalizing"
        db.commit()

        content_service.update_processed(
            content_id=content.id,
            extracted_text=extracted_text,
            title=analysis.get("title"),
            summary=analysis.get("summary"),
            category=analysis.get("category"),
            tags=analysis.get("tags", []),
            importance_score=analysis.get("importance_score", 5),
            actionable=analysis.get("actionable", False),
        )

        embedding_text = " ".join(filter(None, [
            analysis.get("title", ""),
            analysis.get("summary", ""),
            " ".join(analysis.get("tags", [])),
            content.raw_text or "",
        ]))

        if embedding_text.strip():
            vector = ai_service.generate_embedding(embedding_text)
            content_service.create_embedding(content.id, vector)

        elapsed = time.monotonic() - start
        save_task_metric("process_content_task", "success", int(elapsed * 1000), SessionLocal)
        logger.info(
            "process_content_task completed | content_id=%s elapsed=%.2fs title=%r",
            content_id, elapsed, analysis.get("title"),
        )
        send_completion(content, analysis.get("title"))

    except SoftTimeLimitExceeded:
        elapsed = time.monotonic() - start
        logger.error("process_content_task soft time limit | content_id=%s elapsed=%.2fs", content_id, elapsed)
        save_task_metric("process_content_task", "failed", int(elapsed * 1000), SessionLocal)
        try:
            content_service = ContentService(db)
            content_service.mark_failed(UUID(content_id), "Task timed out (soft limit exceeded)")
        except Exception:
            logger.exception("Failed to mark content %s as timed-out", content_id)
        # Do not retry on timeout — the operation is inherently broken
        return

    except MaxRetriesExceededError:
        elapsed = time.monotonic() - start
        logger.error("process_content_task max retries exceeded | content_id=%s elapsed=%.2fs", content_id, elapsed)
        save_task_metric("process_content_task", "failed", int(elapsed * 1000), SessionLocal)
        try:
            content_service = ContentService(db)
            failed_content = content_service.get_by_id(UUID(content_id))
            content_service.mark_failed(UUID(content_id), "Max retries exceeded — permanent failure")
            if failed_content:
                send_failure(failed_content, "Falha permanente após múltiplas tentativas")
        except Exception:
            logger.exception("Failed to mark content %s as failed after max retries", content_id)

    except Exception as exc:
        elapsed = time.monotonic() - start
        logger.exception(
            "process_content_task failed | content_id=%s attempt=%d elapsed=%.2fs error=%s",
            content_id, self.request.retries + 1, elapsed, exc,
        )
        # Persist error for observability but keep status=processing so the retry attempt is clear
        try:
            content_service = ContentService(db)
            content = content_service.get_by_id(UUID(content_id))
            if content:
                content.processing_error = str(exc)[:500]
                db.commit()
        except Exception:
            logger.exception("Failed to persist error for content %s", content_id)

        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

    finally:
        db.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_image_task(self, content_id: str, file_id: str) -> None:
    """Process an image with OCR then analyse with AI."""
    db = SessionLocal()
    temp_file: str | None = None
    start = time.monotonic()
    logger.info("process_image_task started | content_id=%s attempt=%d", content_id, self.request.retries + 1)

    try:
        content_service = ContentService(db)
        ai_service = AIService(db=db)
        telegram_service = TelegramService(db=db)

        content = content_service.get_by_id(UUID(content_id))
        if not content:
            logger.warning("Image content %s not found — skipping", content_id)
            return

        if content.processed:
            logger.info("Image content %s already processed — skipping", content_id)
            return

        # ── Mark processing ────────────────────────────────────────────────
        content_service.mark_processing(UUID(content_id))

        # ── Download from Telegram ─────────────────────────────────────────
        content.processing_stage = "capturing"
        db.commit()
        logger.info("Downloading image from Telegram | content_id=%s file_id=%s", content_id, file_id)
        temp_file, error = asyncio.run(telegram_service.download_photo(file_id))
        if error or not temp_file:
            raise RuntimeError(f"Failed to download image: {error}")

        # ── OCR ────────────────────────────────────────────────────────────
        content.processing_stage = "ocr"
        db.commit()
        logger.info("Running OCR | content_id=%s", content_id)
        extracted_text = extract_text_from_image(temp_file)

        # ── AI analysis ────────────────────────────────────────────────────
        content.processing_stage = "ai_processing"
        db.commit()
        logger.info("Starting AI analysis | content_id=%s", content_id)
        analysis = ai_service.analyze_content(
            content_type="image",
            raw_text=content.raw_text,
            extracted_text=extracted_text,
        )

        content.processing_stage = "finalizing"
        db.commit()

        content_service.update_processed(
            content_id=content.id,
            extracted_text=extracted_text,
            title=analysis.get("title"),
            summary=analysis.get("summary"),
            category=analysis.get("category"),
            tags=analysis.get("tags", []),
            importance_score=analysis.get("importance_score", 5),
            actionable=analysis.get("actionable", False),
        )

        embedding_text = " ".join(filter(None, [
            analysis.get("title", ""),
            analysis.get("summary", ""),
            " ".join(analysis.get("tags", [])),
            extracted_text or "",
            content.raw_text or "",
        ]))

        if embedding_text.strip():
            vector = ai_service.generate_embedding(embedding_text)
            content_service.create_embedding(content.id, vector)

        elapsed = time.monotonic() - start
        save_task_metric("process_image_task", "success", int(elapsed * 1000), SessionLocal)
        logger.info(
            "process_image_task completed | content_id=%s elapsed=%.2fs",
            content_id, elapsed,
        )
        send_completion(content, analysis.get("title"))

    except SoftTimeLimitExceeded:
        elapsed = time.monotonic() - start
        logger.error("process_image_task soft time limit | content_id=%s elapsed=%.2fs", content_id, elapsed)
        save_task_metric("process_image_task", "failed", int(elapsed * 1000), SessionLocal)
        try:
            content_service = ContentService(db)
            content_service.mark_failed(UUID(content_id), "Task timed out")
        except Exception:
            logger.exception("Failed to mark image content %s as timed-out", content_id)
        return

    except MaxRetriesExceededError:
        elapsed = time.monotonic() - start
        logger.error("process_image_task max retries exceeded | content_id=%s elapsed=%.2fs", content_id, elapsed)
        save_task_metric("process_image_task", "failed", int(elapsed * 1000), SessionLocal)
        try:
            content_service = ContentService(db)
            failed_content = content_service.get_by_id(UUID(content_id))
            content_service.mark_failed(UUID(content_id), "Max retries exceeded — permanent failure")
            if failed_content:
                send_failure(failed_content, "Falha ao processar imagem após múltiplas tentativas")
        except Exception:
            logger.exception("Failed to mark image content %s as failed", content_id)

    except Exception as exc:
        elapsed = time.monotonic() - start
        logger.exception(
            "process_image_task failed | content_id=%s attempt=%d elapsed=%.2fs error=%s",
            content_id, self.request.retries + 1, elapsed, exc,
        )
        try:
            content_service = ContentService(db)
            content = content_service.get_by_id(UUID(content_id))
            if content:
                content.processing_error = str(exc)[:500]
                db.commit()
        except Exception:
            logger.exception("Failed to persist error for image content %s", content_id)

        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

    finally:
        db.close()
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except OSError:
                pass


@shared_task(bind=True, max_retries=3, default_retry_delay=60, acks_late=True, reject_on_worker_lost=True)
def process_audio_task(self, content_id: str, file_id: str) -> None:
    """Download a Telegram audio/video file, transcribe via STT, then analyse with AI."""
    db = SessionLocal()
    temp_file: str | None = None
    wav_file: str | None = None
    start = time.monotonic()
    logger.info("process_audio_task started | content_id=%s attempt=%d", content_id, self.request.retries + 1)

    try:
        content_service = ContentService(db)
        ai_service = AIService(db=db)
        telegram_service = TelegramService(db=db)

        content = content_service.get_by_id(UUID(content_id))
        if not content:
            logger.warning("Audio content %s not found — skipping", content_id)
            return
        if content.processed:
            logger.info("Audio content %s already processed — skipping", content_id)
            return

        content_service.mark_processing(UUID(content_id))

        # ── Download ───────────────────────────────────────────────────────
        content.processing_stage = "capturing"
        db.commit()
        logger.info("Downloading audio from Telegram | content_id=%s file_id=%s", content_id, file_id)
        temp_file, error = asyncio.run(telegram_service.download_photo(file_id))
        if error or not temp_file:
            raise RuntimeError(f"Failed to download audio: {error}")

        # ── Audio extraction ───────────────────────────────────────────────
        from app.services.settings_service import SettingsService
        stt_enabled = SettingsService(db).get_bool_value("audio_transcription_enabled")

        transcript_text: str | None = None
        transcript_language: str | None = None

        if stt_enabled:
            content.processing_stage = "audio_extract"
            db.commit()
            logger.info("Extracting audio | content_id=%s", content_id)
            wav_file = extract_audio(temp_file, max_minutes=settings.MAX_AUDIO_MINUTES)

            # ── Transcription ──────────────────────────────────────────────
            content.processing_stage = "transcribing"
            db.commit()
            logger.info("Transcribing audio | content_id=%s", content_id)
            result = transcribe_audio(wav_file, db=db)
            transcript_text = result["text"]
            transcript_language = result["language"]
        else:
            logger.info("STT disabled — skipping transcription | content_id=%s", content_id)

        # ── AI analysis ────────────────────────────────────────────────────
        content.processing_stage = "ai_processing"
        db.commit()
        logger.info("Starting AI analysis | content_id=%s", content_id)
        analysis = ai_service.analyze_content(
            content_type=content.type,
            raw_text=content.raw_text,
            transcript=transcript_text,
        )

        # ── Persist ────────────────────────────────────────────────────────
        content.processing_stage = "finalizing"
        db.commit()

        content_service.update_processed(
            content_id=content.id,
            title=analysis.get("title"),
            summary=analysis.get("summary"),
            category=analysis.get("category"),
            tags=analysis.get("tags", []),
            importance_score=analysis.get("importance_score", 5),
            actionable=analysis.get("actionable", False),
            transcript=transcript_text,
            transcript_language=transcript_language,
        )

        embedding_text = " ".join(filter(None, [
            analysis.get("title", ""),
            analysis.get("summary", ""),
            " ".join(analysis.get("tags", [])),
            transcript_text or "",
            content.raw_text or "",
        ]))
        if embedding_text.strip():
            vector = ai_service.generate_embedding(embedding_text)
            content_service.create_embedding(content.id, vector)

        elapsed = time.monotonic() - start
        save_task_metric("process_audio_task", "success", int(elapsed * 1000), SessionLocal)
        logger.info("process_audio_task completed | content_id=%s elapsed=%.2fs", content_id, elapsed)
        send_completion(content, analysis.get("title"))

    except SoftTimeLimitExceeded:
        elapsed = time.monotonic() - start
        logger.error("process_audio_task soft time limit | content_id=%s elapsed=%.2fs", content_id, elapsed)
        save_task_metric("process_audio_task", "failed", int(elapsed * 1000), SessionLocal)
        try:
            ContentService(db).mark_failed(UUID(content_id), "Task timed out")
        except Exception:
            logger.exception("Failed to mark audio content %s as timed-out", content_id)
        return

    except MaxRetriesExceededError:
        elapsed = time.monotonic() - start
        logger.error("process_audio_task max retries exceeded | content_id=%s elapsed=%.2fs", content_id, elapsed)
        save_task_metric("process_audio_task", "failed", int(elapsed * 1000), SessionLocal)
        try:
            failed_content = ContentService(db).get_by_id(UUID(content_id))
            ContentService(db).mark_failed(UUID(content_id), "Max retries exceeded")
            if failed_content:
                send_failure(failed_content, "Falha ao transcrever áudio após múltiplas tentativas")
        except Exception:
            logger.exception("Failed to mark audio content %s as failed", content_id)

    except Exception as exc:
        elapsed = time.monotonic() - start
        logger.exception(
            "process_audio_task failed | content_id=%s attempt=%d elapsed=%.2fs",
            content_id, self.request.retries + 1, elapsed,
        )
        try:
            content = ContentService(db).get_by_id(UUID(content_id))
            if content:
                content.processing_error = str(exc)[:500]
                db.commit()
        except Exception:
            logger.exception("Failed to persist error for audio content %s", content_id)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

    finally:
        db.close()
        for path in (wav_file, temp_file):
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def reanalyze_content_task(self, content_id: str) -> None:
    """Re-run AI analysis and embedding using existing OCR/transcript data.

    Used when reprocessing media content (image, audio, video) where the
    original file is no longer available for download.
    """
    db = SessionLocal()
    start = time.monotonic()
    logger.info("reanalyze_content_task started | content_id=%s attempt=%d", content_id, self.request.retries + 1)

    try:
        content_service = ContentService(db)
        ai_service = AIService(db=db)

        content = content_service.get_by_id(UUID(content_id))
        if not content:
            logger.warning("Content %s not found — skipping", content_id)
            return
        if content.processed:
            logger.info("Content %s already processed — skipping", content_id)
            return

        content_service.mark_processing(UUID(content_id))

        # ── AI analysis using existing extracted data ───────────────────────
        content.processing_stage = "ai_processing"
        db.commit()
        logger.info("Starting AI re-analysis | content_id=%s type=%s", content_id, content.type)
        analysis = ai_service.analyze_content(
            content_type=content.type,
            raw_text=content.raw_text,
            extracted_text=content.extracted_text,
            transcript=content.transcript,
        )

        # ── Persist ────────────────────────────────────────────────────────
        content.processing_stage = "finalizing"
        db.commit()

        content_service.update_processed(
            content_id=content.id,
            title=analysis.get("title"),
            summary=analysis.get("summary"),
            category=analysis.get("category"),
            tags=analysis.get("tags", []),
            importance_score=analysis.get("importance_score", 5),
            actionable=analysis.get("actionable", False),
        )

        embedding_text = " ".join(filter(None, [
            analysis.get("title", ""),
            analysis.get("summary", ""),
            " ".join(analysis.get("tags", [])),
            content.extracted_text or "",
            content.transcript or "",
            content.raw_text or "",
        ]))
        if embedding_text.strip():
            vector = ai_service.generate_embedding(embedding_text)
            content_service.create_embedding(content.id, vector)

        elapsed = time.monotonic() - start
        save_task_metric("reanalyze_content_task", "success", int(elapsed * 1000), SessionLocal)
        logger.info("reanalyze_content_task completed | content_id=%s elapsed=%.2fs", content_id, elapsed)
        send_completion(content, analysis.get("title"))

    except SoftTimeLimitExceeded:
        elapsed = time.monotonic() - start
        logger.error("reanalyze_content_task soft time limit | content_id=%s elapsed=%.2fs", content_id, elapsed)
        save_task_metric("reanalyze_content_task", "failed", int(elapsed * 1000), SessionLocal)
        try:
            ContentService(db).mark_failed(UUID(content_id), "Task timed out")
        except Exception:
            logger.exception("Failed to mark content %s as timed-out", content_id)
        return

    except MaxRetriesExceededError:
        elapsed = time.monotonic() - start
        logger.error("reanalyze_content_task max retries exceeded | content_id=%s elapsed=%.2fs", content_id, elapsed)
        save_task_metric("reanalyze_content_task", "failed", int(elapsed * 1000), SessionLocal)
        try:
            failed_content = ContentService(db).get_by_id(UUID(content_id))
            ContentService(db).mark_failed(UUID(content_id), "Max retries exceeded")
            if failed_content:
                send_failure(failed_content, "Falha ao reanalisar conteúdo após múltiplas tentativas")
        except Exception:
            logger.exception("Failed to mark content %s as failed", content_id)

    except Exception as exc:
        elapsed = time.monotonic() - start
        logger.exception(
            "reanalyze_content_task failed | content_id=%s attempt=%d elapsed=%.2fs",
            content_id, self.request.retries + 1, elapsed,
        )
        try:
            content = ContentService(db).get_by_id(UUID(content_id))
            if content:
                content.processing_error = str(exc)[:500]
                db.commit()
        except Exception:
            logger.exception("Failed to persist error for content %s", content_id)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

    finally:
        db.close()
