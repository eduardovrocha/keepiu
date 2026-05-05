from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.metrics_service import get_workers_status

router = APIRouter(prefix="/workers", tags=["workers"])


@router.get("/status")
async def workers_status(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Return task throughput metrics and queue depths for the last hour."""
    response.headers["Cache-Control"] = "no-store"
    return get_workers_status(db)
