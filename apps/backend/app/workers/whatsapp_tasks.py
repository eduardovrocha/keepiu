import asyncio
import logging
import os
import time
from uuid import UUID

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded
from sqlalchemy.orm import sessionmaker

from app.core.database import engine
from app.core.config import get_settings
from app.services.content_service import ContentService
from app.services.ai_service import AIService
from app.services.metrics_service import save_task_metric
from app.utils.ocr import extract_text_from_image
from app.utils.audio import extract_audio
from app.utils.transcription import transcribe_audio
from app.workers.notifications import send_completion, send_failure

logger = logging.getLogger(__name__)
settings = get_settings()
SessionLocal = sessionmaker(bind=engine)


@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def process_whatsapp_image_task(self, content_id: str, media_id: str) -> None:
    """Download a WhatsApp image, run OCR and AI analysis, generate embedding."""
    db = SessionLocal()
    temp_file: str | None = None
    start = time.monotonic()
    logger.info(
        "process_whatsapp_image_task started | content_id=%s attempt=%d",
        content_id, self.request.retries + 1,
    )

    try:
        content_service = ContentService(db)
        ai_service = AIService(db=db)

        content = content_service.get_by_id(UUID(content_id))
        if not content:
            logger.warning("WhatsApp image content %s not found — skipping", content_id)
            return
        if content.processed:
            logger.info("WhatsApp image content %s already processed — skipping", content_id)
            return

        content_service.mark_processing(UUID(content_id))

        # ── Download from WhatsApp ─────────────────────────────────────────
        content.processing_stage = "capturing"
        db.commit()
        logger.info("Downloading WhatsApp media | content_id=%s media_id=%s", content_id, media_id)
        from app.services.whatsapp_service import WhatsAppService
        wa = WhatsAppService()
        temp_file, mime_type = asyncio.run(wa.download_media_to_file(media_id))

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
            extracted_text or "",
            content.raw_text or "",
        ]))
        if embedding_text.strip():
            vector = ai_service.generate_embedding(embedding_text)
            content_service.create_embedding(content.id, vector)

        elapsed = time.monotonic() - start
        save_task_metric("process_whatsapp_image_task", "success", int(elapsed * 1000), SessionLocal)
        logger.info(
            "process_whatsapp_image_task completed | content_id=%s elapsed=%.2fs",
            content_id, elapsed,
        )
        send_completion(content, analysis.get("title"))

    except SoftTimeLimitExceeded:
        elapsed = time.monotonic() - start
        logger.error(
            "process_whatsapp_image_task soft time limit | content_id=%s elapsed=%.2fs",
            content_id, elapsed,
        )
        save_task_metric("process_whatsapp_image_task", "failed", int(elapsed * 1000), SessionLocal)
        try:
            ContentService(db).mark_failed(UUID(content_id), "Task timed out")
        except Exception:
            logger.exception("Failed to mark WhatsApp image content %s as timed-out", content_id)
        return

    except MaxRetriesExceededError:
        elapsed = time.monotonic() - start
        logger.error(
            "process_whatsapp_image_task max retries | content_id=%s elapsed=%.2fs",
            content_id, elapsed,
        )
        save_task_metric("process_whatsapp_image_task", "failed", int(elapsed * 1000), SessionLocal)
        try:
            failed_content = ContentService(db).get_by_id(UUID(content_id))
            ContentService(db).mark_failed(UUID(content_id), "Max retries exceeded")
            if failed_content:
                send_failure(failed_content, "Falha ao processar imagem WhatsApp após múltiplas tentativas")
        except Exception:
            logger.exception("Failed to mark WhatsApp image content %s as failed", content_id)

    except Exception as exc:
        elapsed = time.monotonic() - start
        logger.exception(
            "process_whatsapp_image_task failed | content_id=%s attempt=%d elapsed=%.2fs",
            content_id, self.request.retries + 1, elapsed,
        )
        try:
            content = ContentService(db).get_by_id(UUID(content_id))
            if content:
                content.processing_error = str(exc)[:500]
                db.commit()
        except Exception:
            logger.exception("Failed to persist error for WhatsApp image content %s", content_id)

        raise self.retry(exc=exc, countdown=30 * 2 ** self.request.retries)

    finally:
        db.close()
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except OSError:
                pass


@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def process_whatsapp_audio_task(self, content_id: str, media_id: str) -> None:
    """Download a WhatsApp audio/video message, transcribe via STT, then analyse with AI."""
    db = SessionLocal()
    temp_file: str | None = None
    wav_file: str | None = None
    start = time.monotonic()
    logger.info(
        "process_whatsapp_audio_task started | content_id=%s attempt=%d",
        content_id, self.request.retries + 1,
    )

    try:
        content_service = ContentService(db)
        ai_service = AIService(db=db)

        content = content_service.get_by_id(UUID(content_id))
        if not content:
            logger.warning("WhatsApp audio content %s not found — skipping", content_id)
            return
        if content.processed:
            logger.info("WhatsApp audio content %s already processed — skipping", content_id)
            return

        content_service.mark_processing(UUID(content_id))

        # ── Download from WhatsApp ─────────────────────────────────────────
        content.processing_stage = "capturing"
        db.commit()
        logger.info("Downloading WhatsApp media | content_id=%s media_id=%s", content_id, media_id)
        from app.services.whatsapp_service import WhatsAppService
        wa = WhatsAppService()
        temp_file, mime_type = asyncio.run(wa.download_media_to_file(media_id))

        # ── Check STT setting ──────────────────────────────────────────────
        from app.services.settings_service import SettingsService
        stt_enabled = SettingsService(db).get_bool_value("audio_transcription_enabled")

        transcript_text: str | None = None
        transcript_language: str | None = None

        if stt_enabled:
            # ── Audio extraction ───────────────────────────────────────────
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
        save_task_metric("process_whatsapp_audio_task", "success", int(elapsed * 1000), SessionLocal)
        logger.info(
            "process_whatsapp_audio_task completed | content_id=%s elapsed=%.2fs",
            content_id, elapsed,
        )
        send_completion(content, analysis.get("title"))

    except SoftTimeLimitExceeded:
        elapsed = time.monotonic() - start
        logger.error(
            "process_whatsapp_audio_task soft time limit | content_id=%s elapsed=%.2fs",
            content_id, elapsed,
        )
        save_task_metric("process_whatsapp_audio_task", "failed", int(elapsed * 1000), SessionLocal)
        try:
            ContentService(db).mark_failed(UUID(content_id), "Task timed out")
        except Exception:
            logger.exception("Failed to mark WhatsApp audio content %s as timed-out", content_id)
        return

    except MaxRetriesExceededError:
        elapsed = time.monotonic() - start
        logger.error(
            "process_whatsapp_audio_task max retries | content_id=%s elapsed=%.2fs",
            content_id, elapsed,
        )
        save_task_metric("process_whatsapp_audio_task", "failed", int(elapsed * 1000), SessionLocal)
        try:
            failed_content = ContentService(db).get_by_id(UUID(content_id))
            ContentService(db).mark_failed(UUID(content_id), "Max retries exceeded")
            if failed_content:
                send_failure(failed_content, "Falha ao transcrever áudio WhatsApp após múltiplas tentativas")
        except Exception:
            logger.exception("Failed to mark WhatsApp audio content %s as failed", content_id)

    except Exception as exc:
        elapsed = time.monotonic() - start
        logger.exception(
            "process_whatsapp_audio_task failed | content_id=%s attempt=%d elapsed=%.2fs",
            content_id, self.request.retries + 1, elapsed,
        )
        try:
            content = ContentService(db).get_by_id(UUID(content_id))
            if content:
                content.processing_error = str(exc)[:500]
                db.commit()
        except Exception:
            logger.exception("Failed to persist error for WhatsApp audio content %s", content_id)
        raise self.retry(exc=exc, countdown=30 * 2 ** self.request.retries)

    finally:
        db.close()
        for path in (wav_file, temp_file):
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
