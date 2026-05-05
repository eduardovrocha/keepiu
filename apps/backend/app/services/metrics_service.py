import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.models.task_metric import TaskMetric

logger = logging.getLogger(__name__)

KNOWN_TASKS: dict[str, str] = {
    "process_instagram_task": "Instagram",
    "process_content_task": "Conteúdo",
    "process_image_task": "Imagem",
    "process_whatsapp_image_task": "WhatsApp",
}


def save_task_metric(
    task_name: str,
    status: str,
    duration_ms: int,
    SessionLocal=None,
) -> None:
    """Persist a task execution metric. Creates its own session — safe to call in error handlers."""
    if SessionLocal is None:
        from app.core.database import engine
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(bind=engine)

    db: Session = SessionLocal()
    try:
        metric = TaskMetric(task_name=task_name, status=status, duration_ms=duration_ms)
        db.add(metric)
        db.commit()
    except Exception:
        logger.exception("Failed to persist task metric task_name=%s status=%s", task_name, status)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def get_workers_status(db: Session) -> dict:
    """Return task metrics aggregated over the last hour plus active/queued counts."""
    from app.models.content import Content

    one_hour_ago = datetime.utcnow() - timedelta(hours=1)

    # ── Per-task metrics ──────────────────────────────────────────────────────
    rows = (
        db.query(
            TaskMetric.task_name,
            func.count().label("total"),
            func.avg(TaskMetric.duration_ms).label("avg_duration_ms"),
            func.sum(
                case((TaskMetric.status == "failed", 1), else_=0)
            ).label("failed_count"),
        )
        .filter(TaskMetric.created_at >= one_hour_ago)
        .group_by(TaskMetric.task_name)
        .all()
    )

    metrics_by_task: dict[str, dict] = {}
    for row in rows:
        total = row.total or 0
        failed = int(row.failed_count or 0)
        avg_ms = int(row.avg_duration_ms) if row.avg_duration_ms else None
        metrics_by_task[row.task_name] = {
            "processed_last_1h": total,
            "avg_duration_ms": avg_ms,
            "error_rate": round(failed / total, 4) if total > 0 else 0.0,
        }

    tasks = []
    for task_name, display_name in KNOWN_TASKS.items():
        m = metrics_by_task.get(task_name, {})
        tasks.append(
            {
                "name": display_name,
                "task_name": task_name,
                "avg_duration_ms": m.get("avg_duration_ms"),
                "error_rate": m.get("error_rate", 0.0),
                "processed_last_1h": m.get("processed_last_1h", 0),
            }
        )

    # ── Global totals ─────────────────────────────────────────────────────────
    active_count = (
        db.query(func.count(Content.id))
        .filter(Content.status == "processing")
        .scalar()
        or 0
    )
    queued_count = (
        db.query(func.count(Content.id))
        .filter(Content.status == "queued")
        .scalar()
        or 0
    )

    total_last_1h = sum(t["processed_last_1h"] for t in tasks)
    total_failed_last_1h = sum(
        int((m.get("error_rate", 0) * m.get("processed_last_1h", 0)))
        for m in metrics_by_task.values()
    )
    global_error_rate = (
        round(total_failed_last_1h / total_last_1h, 4) if total_last_1h > 0 else 0.0
    )

    return {
        "tasks": tasks,
        "totals": {
            "active": active_count,
            "queued": queued_count,
            "processed_last_1h": total_last_1h,
            "error_rate": global_error_rate,
        },
    }
