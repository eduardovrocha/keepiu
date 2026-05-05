from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.content_service import ContentService
from app.schemas.dashboard import DashboardStats, CategoryStat
from app.core.cache import cache_get, cache_set

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_STATS_TTL = 60  # seconds


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cache_key = f"dashboard:stats:{current_user.id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return DashboardStats(**cached)

    content_service = ContentService(db)
    stats = content_service.get_dashboard_stats(current_user.id)

    result = DashboardStats(
        total_contents=stats["total_contents"],
        processed_contents=stats["processed_contents"],
        pending_contents=stats["pending_contents"],
        recent_contents=stats["recent_contents"],
        average_importance_score=stats["average_importance_score"],
        top_categories=[
            CategoryStat(category=c["category"], count=c["count"])
            for c in stats["top_categories"]
        ]
    )

    cache_set(cache_key, result.model_dump(), _STATS_TTL)
    return result
