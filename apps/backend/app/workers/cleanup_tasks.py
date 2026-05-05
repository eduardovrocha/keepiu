import logging
from datetime import datetime, timedelta

from celery import shared_task
from sqlalchemy.orm import sessionmaker

from app.core.database import engine
from app.models.task_metric import TaskMetric
from app.models.content import Content
from app.models.refresh_token import RefreshToken

logger = logging.getLogger(__name__)
SessionLocal = sessionmaker(bind=engine)


@shared_task
def cleanup_old_task_metrics() -> dict:
    """Delete task_metrics rows older than 7 days."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    db = SessionLocal()
    try:
        deleted = (
            db.query(TaskMetric)
            .filter(TaskMetric.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info("cleanup_old_task_metrics: deleted %d rows (cutoff=%s)", deleted, cutoff.date())
        return {"deleted_metrics": deleted}
    except Exception:
        db.rollback()
        logger.exception("cleanup_old_task_metrics failed")
        raise
    finally:
        db.close()


@shared_task
def cleanup_expired_refresh_tokens() -> dict:
    """Purge refresh token rows that are expired or revoked, older than 1 day."""
    cutoff = datetime.utcnow() - timedelta(days=1)
    db = SessionLocal()
    try:
        deleted = (
            db.query(RefreshToken)
            .filter(
                (RefreshToken.expires_at < cutoff) | (RefreshToken.revoked == True)  # noqa: E712
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info("cleanup_expired_refresh_tokens: deleted %d rows", deleted)
        return {"deleted_refresh_tokens": deleted}
    except Exception:
        db.rollback()
        logger.exception("cleanup_expired_refresh_tokens failed")
        raise
    finally:
        db.close()


@shared_task
def cleanup_old_content() -> dict:
    """Delete completed/failed content older than CONTENT_RETENTION_DAYS. Disabled when 0."""
    from app.core.config import get_settings
    settings = get_settings()

    retention_days = settings.CONTENT_RETENTION_DAYS
    if not retention_days:
        return {"skipped": True, "reason": "CONTENT_RETENTION_DAYS=0"}

    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    db = SessionLocal()
    try:
        deleted = (
            db.query(Content)
            .filter(
                Content.status.in_(["completed", "failed"]),
                Content.created_at < cutoff,
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(
            "cleanup_old_content: deleted %d items older than %d days (cutoff=%s)",
            deleted, retention_days, cutoff.date(),
        )
        return {"deleted_contents": deleted}
    except Exception:
        db.rollback()
        logger.exception("cleanup_old_content failed")
        raise
    finally:
        db.close()
