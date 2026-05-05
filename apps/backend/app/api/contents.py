from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.content import Content
from app.services.content_service import ContentService
from app.schemas.content import ContentResponse, ContentListResponse, ContentUpdate, ContentSubmit, ContentCreate, ContentProcessingResponse

router = APIRouter(prefix="/contents", tags=["contents"])


@router.post("", response_model=ContentResponse, status_code=status.HTTP_201_CREATED)
async def submit_content(
    body: ContentSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a URL for processing (web UI direct ingestion)."""
    from app.services.source_detector import detect_source
    from app.workers.instagram_tasks import process_instagram_task

    detected_platform = detect_source(body.source_url)

    content_service = ContentService(db)

    existing = content_service.get_by_url(current_user.id, body.source_url)
    if existing:
        return ContentResponse.model_validate(existing)

    allowed, quota_info = content_service.check_quota(current_user.id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "quota_exceeded",
                "plan": quota_info["plan"],
                "contents_this_month": quota_info["contents_this_month"],
                "max_contents_per_month": quota_info["max_contents_per_month"],
                "total_contents": quota_info["total_contents"],
                "max_total_contents": quota_info["max_total_contents"],
            },
        )

    content_data = ContentCreate(
        user_id=current_user.id,
        source="web",
        type="link",
        url=body.source_url,
        raw_text=body.source_url,
        source_platform=detected_platform if detected_platform != "unknown" else None,
        ingestion_channel="web",
    )
    content = content_service.create(content_data)
    content_service.increment_quota(current_user.id)

    from app.core.processing import route_task
    if detected_platform == "instagram":
        route_task(process_instagram_task, str(content.id))
    else:
        from app.workers.content_processor import process_content_task
        route_task(process_content_task, str(content.id))

    return ContentResponse.model_validate(content)


@router.get("", response_model=ContentListResponse)
async def list_contents(
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    content_type: Optional[str] = Query(None, alias="type"),
    processed: Optional[bool] = None,
    ingestion_channel: Optional[str] = None,
    source_platform: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's contents with filters and pagination."""
    response.headers["Cache-Control"] = "no-store"
    content_service = ContentService(db)

    skip = (page - 1) * page_size
    contents, total = content_service.get_user_contents(
        user_id=current_user.id,
        skip=skip,
        limit=page_size,
        category=category,
        content_type=content_type,
        processed=processed,
        status=status,
        ingestion_channel=ingestion_channel,
        source_platform=source_platform,
    )
    
    return ContentListResponse(
        items=[ContentResponse.model_validate(c) for c in contents],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/processing", response_model=list[ContentProcessingResponse])
async def list_processing(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    """Return all items currently being processed for the current user (max 50)."""
    response.headers["Cache-Control"] = "no-store"
    from app.models.content import Content as ContentModel
    from sqlalchemy import desc

    items = (
        db.query(ContentModel)
        .filter(
            ContentModel.user_id == current_user.id,
            ContentModel.status.in_(["queued", "processing"]),
        )
        .order_by(desc(ContentModel.created_at))
        .limit(50)
        .all()
    )
    return [ContentProcessingResponse.model_validate(i) for i in items]


@router.get("/{content_id}", response_model=ContentResponse)
async def get_content(
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific content by ID."""
    content_service = ContentService(db)
    content = content_service.get_by_id(content_id)
    
    if not content or content.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    return ContentResponse.model_validate(content)


@router.put("/{content_id}", response_model=ContentResponse)
async def update_content(
    content_id: UUID,
    update_data: ContentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a content."""
    content_service = ContentService(db)
    content = content_service.get_by_id(content_id)
    
    if not content or content.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    updated = content_service.update(content_id, update_data)
    return ContentResponse.model_validate(updated)


_REPROCESS_COOLDOWN_SECONDS = 10


@router.post("/{content_id}/reprocess")
async def reprocess_content(
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-queue a content item for full reprocessing.

    Text/link: re-runs full pipeline (extract → AI → embedding).
    Image/audio/video: re-runs AI + embedding using existing OCR/transcript,
    since the original media file is no longer available.
    """
    from datetime import datetime, timedelta
    from app.core.processing import route_task
    from app.models.content import ContentEmbedding

    content_service = ContentService(db)
    content = content_service.get_by_id(content_id)

    if not content or content.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")

    # Guard: reject if already in flight
    if content.status == "processing":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content is already being processed")

    # Guard: rate limit per item
    if content.last_reprocess_at and (
        datetime.utcnow() - content.last_reprocess_at
    ) < timedelta(seconds=_REPROCESS_COOLDOWN_SECONDS):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {_REPROCESS_COOLDOWN_SECONDS}s before reprocessing again",
        )

    # ── Reset AI-derived fields ────────────────────────────────────────────
    content.title = None
    content.summary = None
    content.category = None
    content.tags = []
    content.importance_score = 0
    content.actionable = False
    content.processing_error = None
    content.processing_stage = "queued"
    content.status = "queued"
    content.processed = False
    content.processing_started_at = None
    content.processed_at = None
    content.last_reprocess_at = datetime.utcnow()

    # For text/link we can fully re-extract, so clear those fields too
    if content.type in ("text", "link"):
        content.extracted_text = None
        content.transcript = None
        content.transcript_language = None

    # ── Delete stale embedding ─────────────────────────────────────────────
    stale_embedding = (
        db.query(ContentEmbedding)
        .filter(ContentEmbedding.content_id == content.id)
        .first()
    )
    if stale_embedding:
        db.delete(stale_embedding)

    db.commit()

    # ── Route to the correct worker ───────────────────────────────────────
    if content.type in ("text", "link"):
        from app.workers.content_processor import process_content_task
        route_task(process_content_task, str(content_id))
    else:
        # image / audio / video — re-run AI only (media file unavailable)
        from app.workers.content_processor import reanalyze_content_task
        route_task(reanalyze_content_task, str(content_id))

    return {"requeued": True, "content_id": str(content_id)}


@router.delete("/{content_id}")
async def delete_content(
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a content."""
    content_service = ContentService(db)
    content = content_service.get_by_id(content_id)
    
    if not content or content.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    success = content_service.delete(content_id)
    if success:
        return {"deleted": True}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete content"
        )
