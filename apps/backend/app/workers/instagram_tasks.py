import asyncio
import logging
import time
from datetime import datetime
from uuid import UUID

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded
from sqlalchemy.orm import sessionmaker

from app.core.database import engine
from app.services.content_service import ContentService
from app.services.instagram_ai_service import InstagramAIService
from app.services.instagram_agent import capture_instagram_post
from app.services.metrics_service import save_task_metric
from app.utils.ocr import extract_text_from_bytes

logger = logging.getLogger(__name__)
SessionLocal = sessionmaker(bind=engine)

# Only TIMEOUT is transient; LOGIN_REQUIRED and NOT_FOUND are permanent failures
_RETRYABLE_ERRORS = {"TIMEOUT"}


def _run_ocr_on_carousel(carousel_items) -> tuple[list[dict], list[str], float | None]:
    """
    Run OCR on every IMAGE slide in carousel_items.

    Returns:
        ocr_blocks  – list of {index, text, confidence} dicts (for DB storage)
        ocr_texts   – ordered list of extracted texts (for AI input)
        avg_confidence – mean OCR confidence across blocks, or None
    """
    ocr_blocks: list[dict] = []
    ocr_texts: list[str] = []

    for item in carousel_items:
        if item.media_type != "IMAGE" or not item.image_bytes:
            continue

        extracted_text, confidence = extract_text_from_bytes(item.image_bytes)
        if not extracted_text or confidence < 0.3:
            logger.debug("OCR low-confidence or empty | slide=%d conf=%.2f", item.index, confidence)
            continue

        ocr_blocks.append({
            "index": item.index,
            "text": extracted_text,
            "confidence": round(confidence, 3),
        })
        ocr_texts.append(extracted_text)
        logger.debug("OCR slide %d | chars=%d conf=%.2f", item.index, len(extracted_text), confidence)

    avg_conf: float | None = None
    if ocr_blocks:
        avg_conf = sum(b["confidence"] for b in ocr_blocks) / len(ocr_blocks)

    return ocr_blocks, ocr_texts, avg_conf


@shared_task(
    bind=True,
    max_retries=3,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_instagram_task(self, content_id: str) -> None:
    """
    Capture a public Instagram post via headless browser, run OCR on every
    slide (carousel support), then AI analyse and store results.
    Retried up to 3x with exponential backoff for timeouts.
    """
    db = SessionLocal()
    start = time.monotonic()
    logger.info(
        "process_instagram_task started | content_id=%s attempt=%d",
        content_id, self.request.retries + 1,
    )

    try:
        content_service = ContentService(db)

        content = content_service.get_by_id(UUID(content_id))
        if not content:
            logger.warning("Instagram content %s not found — skipping", content_id)
            return

        if content.processed:
            logger.info("Instagram content %s already processed — skipping", content_id)
            return

        content_service.mark_processing(UUID(content_id))

        # ── Browser capture ────────────────────────────────────────────────
        content.processing_stage = "capturing"
        db.commit()
        url = content.url or content.raw_text or ""
        logger.info(
            "Capturing Instagram post | content_id=%s url=%s", content_id, url
        )
        result = asyncio.run(capture_instagram_post(url))

        if not result.success:
            logger.warning(
                "Instagram capture failed | content_id=%s error_type=%s message=%s",
                content_id, result.error_type, result.error_message,
            )
            if result.error_type in _RETRYABLE_ERRORS:
                raise self.retry(
                    exc=RuntimeError(result.error_message),
                    countdown=30 * 2 ** self.request.retries,
                )
            content_service.mark_failed(
                UUID(content_id),
                result.error_message or result.error_type or "Unknown capture error",
            )
            return

        logger.info(
            "Capture succeeded | content_id=%s slides=%d is_carousel=%s",
            content_id, len(result.carousel_items), result.is_carousel,
        )

        # ── OCR — every carousel slide ─────────────────────────────────────
        ocr_blocks: list[dict] = []
        ocr_texts: list[str] = []
        confidence_ocr: float | None = None

        if result.carousel_items:
            content.processing_stage = "ocr"
            db.commit()
            logger.info(
                "Running OCR | content_id=%s slides=%d",
                content_id, len(result.carousel_items),
            )
            ocr_blocks, ocr_texts, confidence_ocr = _run_ocr_on_carousel(result.carousel_items)
            logger.info(
                "OCR complete | content_id=%s blocks=%d avg_conf=%s",
                content_id, len(ocr_blocks),
                f"{confidence_ocr:.2f}" if confidence_ocr else "n/a",
            )

        # ── Instagram AI analysis ──────────────────────────────────────────
        content.processing_stage = "ai_processing"
        db.commit()
        logger.info("Running Instagram AI analysis | content_id=%s", content_id)
        ai_service = InstagramAIService(db=db)
        analysis = ai_service.analyze(
            caption=result.caption or "",
            ocr_texts=ocr_texts,
            username=result.username,
            media_type="carousel" if result.is_carousel else "image",
            permalink=url,
            slide_count=len(result.carousel_items) if result.is_carousel else 1,
        )

        # ── Persist ────────────────────────────────────────────────────────
        content.processing_stage = "finalizing"
        db.commit()

        # Aggregate OCR text for extracted_text field (all slides joined)
        ocr_text_str = "\n\n".join(ocr_texts) if ocr_texts else None
        derived_title = (result.caption or "")[:80].strip() or "Instagram post"

        content_service.update_processed(
            content_id=content.id,
            extracted_text=ocr_text_str,
            title=derived_title,
            summary=analysis.get("summary"),
            category=analysis.get("niche"),
            tags=analysis.get("tags", []),
            importance_score=7,
            actionable=bool(analysis.get("cta")),
        )

        # ── Persist Instagram-specific fields + ocr_blocks ─────────────────
        content = content_service.get_by_id(UUID(content_id))
        if content:
            content.caption = result.caption
            content.tone = analysis.get("tone")
            content.niche = analysis.get("niche")
            content.cta = analysis.get("cta")
            content.language_detected = analysis.get("language_detected")
            content.sentiment_score = analysis.get("sentiment_score")
            content.external_id = result.shortcode
            content.instagram_agent_processed = True
            content.ocr_blocks = ocr_blocks if ocr_blocks else None
            if confidence_ocr is not None:
                content.confidence_score_ocr = confidence_ocr
            content.updated_at = datetime.utcnow()
            db.commit()

        # ── Embedding ──────────────────────────────────────────────────────
        from app.services.ai_service import AIService
        ai_gen = AIService(db=db)
        embedding_text = " ".join(filter(None, [
            derived_title,
            analysis.get("summary", ""),
            " ".join(analysis.get("tags", [])),
            result.caption or "",
            ocr_text_str or "",
        ]))
        if embedding_text.strip():
            vector = ai_gen.generate_embedding(embedding_text)
            content_service.create_embedding(UUID(content_id), vector)

        elapsed = time.monotonic() - start
        save_task_metric("process_instagram_task", "success", int(elapsed * 1000), SessionLocal)
        logger.info(
            "process_instagram_task completed | content_id=%s elapsed=%.2fs shortcode=%s slides=%d",
            content_id, elapsed, result.shortcode, len(result.carousel_items),
        )

    except SoftTimeLimitExceeded:
        elapsed = time.monotonic() - start
        logger.error(
            "process_instagram_task soft time limit | content_id=%s elapsed=%.2fs",
            content_id, elapsed,
        )
        save_task_metric("process_instagram_task", "failed", int(elapsed * 1000), SessionLocal)
        try:
            ContentService(db).mark_failed(UUID(content_id), "Task timed out")
        except Exception:
            logger.exception("Failed to mark instagram content %s as timed-out", content_id)
        return

    except MaxRetriesExceededError:
        elapsed = time.monotonic() - start
        logger.error(
            "process_instagram_task max retries exceeded | content_id=%s elapsed=%.2fs",
            content_id, elapsed,
        )
        save_task_metric("process_instagram_task", "failed", int(elapsed * 1000), SessionLocal)
        try:
            ContentService(db).mark_failed(UUID(content_id), "Max retries exceeded")
        except Exception:
            logger.exception(
                "Failed to mark instagram content %s as failed after max retries", content_id
            )

    except Exception as exc:
        elapsed = time.monotonic() - start
        logger.exception(
            "process_instagram_task failed | content_id=%s attempt=%d elapsed=%.2fs error=%s",
            content_id, self.request.retries + 1, elapsed, exc,
        )
        try:
            c = ContentService(db).get_by_id(UUID(content_id))
            if c:
                c.processing_error = str(exc)[:500]
                db.commit()
        except Exception:
            logger.exception(
                "Failed to persist error for instagram content %s", content_id
            )
        raise self.retry(exc=exc, countdown=30 * 2 ** self.request.retries)

    finally:
        db.close()
