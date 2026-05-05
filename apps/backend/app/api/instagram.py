import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.content_service import ContentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/instagram", tags=["instagram"])

MAX_BATCH_SIZE = 20


@router.post("/process-batch")
async def process_instagram_batch(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Queue all unprocessed Instagram items for the current user (max 20 per call)."""
    from app.workers.instagram_tasks import process_instagram_task
    from app.core.processing import route_task

    content_service = ContentService(db)
    items = content_service.get_instagram_pending(current_user.id, max_count=MAX_BATCH_SIZE)

    for item in items:
        route_task(process_instagram_task, str(item.id))

    logger.info(
        "instagram_batch_triggered user_id=%s batch_size=%d",
        current_user.id,
        len(items),
    )

    return {"queued": len(items)}
