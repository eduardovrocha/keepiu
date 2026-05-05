from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "keepiu",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.content_processor",
        "app.workers.whatsapp_tasks",
        "app.workers.instagram_tasks",
        "app.workers.cleanup_tasks",
    ],
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Time
    timezone="UTC",
    enable_utc=True,

    # ── THE PRIMARY FIX ────────────────────────────────────────────────────
    # Without this, .delay() sends to the "celery" queue by default.
    # The worker only listens to "default" and "processing", so tasks were
    # piling up in "celery" and never consumed.
    task_default_queue="default",
    task_routes={
        "app.workers.content_processor.process_content_task": {"queue": "default"},
        "app.workers.content_processor.process_image_task": {"queue": "processing"},
        "app.workers.whatsapp_tasks.process_whatsapp_image_task": {"queue": "processing"},
        "app.workers.instagram_tasks.process_instagram_task": {"queue": "processing"},
    },
    # ────────────────────────────────────────────────────────────────────────

    # Reliability: only ACK after the task function returns successfully.
    # If the worker crashes mid-task the message is re-delivered.
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Visibility
    task_track_started=True,

    # Timeouts — hard kill after 5 min, soft signal at 4 min
    task_time_limit=300,
    task_soft_time_limit=240,

    # Prevent worker from pre-fetching more tasks than it can handle
    worker_prefetch_multiplier=1,
    worker_concurrency=2,

    # Suppress the startup deprecation warning
    broker_connection_retry_on_startup=True,

    # Beat schedule
    beat_schedule={
        "cleanup-old-task-metrics": {
            "task": "app.workers.cleanup_tasks.cleanup_old_task_metrics",
            "schedule": 86400,
            "options": {"queue": "default"},
        },
        "cleanup-expired-refresh-tokens": {
            "task": "app.workers.cleanup_tasks.cleanup_expired_refresh_tokens",
            "schedule": 3600,   # hourly
            "options": {"queue": "default"},
        },
        "cleanup-old-content": {
            "task": "app.workers.cleanup_tasks.cleanup_old_content",
            "schedule": 86400,
            "options": {"queue": "default"},
        },
    },
)
