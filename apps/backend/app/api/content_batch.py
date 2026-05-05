import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.content_service import ContentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/content", tags=["content-batch"])

MAX_BATCH_SIZE = 20


@router.post("/process-batch")
async def process_content_batch(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Queue all pending content items for processing.
    Routes each item to the correct agent based on source_platform.
    Items with no agent yet are skipped silently.
    """
    from app.workers.instagram_tasks import process_instagram_task
    from app.core.processing import route_task

    content_service = ContentService(db)
    items = content_service.get_pending_for_batch(current_user.id, max_count=MAX_BATCH_SIZE)

    queued = 0
    for item in items:
        platform = item.source_platform or "unknown"
        if platform == "instagram":
            route_task(process_instagram_task, str(item.id))
            queued += 1
        elif platform in ("youtube", "linkedin"):
            logger.info(
                "No agent for %s yet — skipping | content_id=%s",
                platform,
                item.id,
            )
        else:
            logger.info(
                "Unknown source_platform %r — skipping | content_id=%s",
                platform,
                item.id,
            )

    logger.info(
        "content_batch_triggered user_id=%s total_eligible=%d queued=%d",
        current_user.id,
        len(items),
        queued,
    )

    return {"queued": queued}
