"""Task routing helper.

In PROCESSING_MODE=worker (default): dispatches tasks to the Celery queue.
In PROCESSING_MODE=inline: runs the task body in a background thread so the
  HTTP response can return immediately without requiring Redis or a worker process.
"""
import concurrent.futures
import logging
from typing import Any, Callable

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="inline-task")


def route_task(celery_task: Any, *args: Any, **kwargs: Any) -> None:
    """Dispatch a task via Celery (worker mode) or run it inline (inline mode)."""
    settings = get_settings()

    if settings.PROCESSING_MODE == "inline":
        _executor.submit(_run_inline, celery_task, args, kwargs)
    else:
        celery_task.delay(*args, **kwargs)


def _run_inline(celery_task: Any, args: tuple, kwargs: dict) -> None:
    """Run a Celery task synchronously using .apply(), which correctly injects `self`
    for bind=True tasks without going through the broker."""
    try:
        celery_task.apply(args=args, kwargs=kwargs)
    except Exception:
        logger.exception(
            "Inline task failed | task=%s args=%s",
            getattr(celery_task, "name", celery_task),
            args,
        )
