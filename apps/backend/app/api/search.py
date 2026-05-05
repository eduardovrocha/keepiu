import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.cache import cache_get, cache_set
from app.core.database import get_db
from app.models.content import Content, ContentEmbedding
from app.models.user import User
from app.schemas.search import SearchQuery, SearchResult
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

_CATEGORIES_TTL = 300  # 5 minutes


def _user_key(request: Request) -> str:
    user: User = request.state.current_user if hasattr(request.state, "current_user") else None
    if user:
        return str(user.id)
    from slowapi.util import get_remote_address
    return get_remote_address(request)


limiter = Limiter(key_func=_user_key)


@router.post("/semantic", response_model=List[SearchResult])
@limiter.limit("30/minute")
async def semantic_search(
    request: Request,
    query: SearchQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Attach user to request state so _user_key can read it
    request.state.current_user = current_user

    ai_service = AIService()
    query_embedding = ai_service.generate_embedding(query.query)

    results = db.query(
        Content.id,
        Content.title,
        Content.summary,
        Content.category,
        Content.type,
        Content.tags,
        Content.created_at,
        ContentEmbedding.vector.l2_distance(query_embedding).label("distance")
    ).join(
        ContentEmbedding, Content.id == ContentEmbedding.content_id
    ).filter(
        Content.user_id == current_user.id
    )

    if query.category:
        results = results.filter(Content.category == query.category)

    results = results.order_by("distance").limit(query.limit).all()

    return [
        SearchResult(
            id=r.id,
            title=r.title,
            summary=r.summary,
            category=r.category,
            type=r.type,
            tags=r.tags or [],
            similarity_score=1 / (1 + float(r.distance)),
            created_at=r.created_at.isoformat() if r.created_at else None
        )
        for r in results
    ]


@router.get("/categories")
async def list_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cache_key = f"search:categories:{current_user.id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    categories = db.query(
        Content.category,
        func.count(Content.id).label("count")
    ).filter(
        Content.user_id == current_user.id,
        Content.category.isnot(None)
    ).group_by(
        Content.category
    ).order_by(func.count(Content.id).desc()).all()

    result = [{"category": cat, "count": count} for cat, count in categories]
    cache_set(cache_key, result, _CATEGORIES_TTL)
    return result
