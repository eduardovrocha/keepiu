from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.models.content import Content, ContentEmbedding
from app.models.plan import Plan
from app.models.user_quota import UserQuota
from app.schemas.content import ContentCreate, ContentUpdate
from uuid import UUID

# Valid status values
STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


class ContentService:
    def __init__(self, db: Session):
        self.db = db

    def get_by_url(self, user_id: UUID, url: str) -> Optional[Content]:
        """Return an existing content item with the same URL for this user, if any."""
        return (
            self.db.query(Content)
            .filter(Content.user_id == user_id, Content.url == url)
            .first()
        )

    # ── Quota helpers ──────────────────────────────────────────────────────

    def _get_or_create_quota(self, user_id: UUID) -> UserQuota:
        """Return (or lazily create) the UserQuota for this user on the free plan."""
        quota = self.db.query(UserQuota).filter(UserQuota.user_id == user_id).first()
        if quota:
            return quota

        from app.core.config import get_settings
        settings = get_settings()
        plan = self.db.query(Plan).filter(Plan.name == settings.DEFAULT_PLAN_NAME).first()
        if not plan:
            # Fallback: any active plan
            plan = self.db.query(Plan).filter(Plan.is_active == True).first()  # noqa: E712

        first_next_month = (datetime.utcnow().replace(day=1) + timedelta(days=32)).replace(day=1)
        quota = UserQuota(
            user_id=user_id,
            plan_id=plan.id,
            contents_this_month=0,
            total_contents=0,
            month_reset_at=first_next_month,
        )
        self.db.add(quota)
        self.db.commit()
        self.db.refresh(quota)
        return quota

    def check_quota(self, user_id: UUID) -> tuple[bool, dict]:
        """Return (allowed, info). Resets monthly counter if needed."""
        quota = self._get_or_create_quota(user_id)
        plan = self.db.query(Plan).filter(Plan.id == quota.plan_id).first()

        # Monthly reset
        if quota.month_reset_at <= datetime.utcnow():
            first_next_month = (datetime.utcnow().replace(day=1) + timedelta(days=32)).replace(day=1)
            quota.contents_this_month = 0
            quota.month_reset_at = first_next_month
            self.db.commit()

        monthly_ok = plan.max_contents_per_month is None or quota.contents_this_month < plan.max_contents_per_month
        total_ok = plan.max_total_contents is None or quota.total_contents < plan.max_total_contents

        info = {
            "plan": plan.name,
            "contents_this_month": quota.contents_this_month,
            "max_contents_per_month": plan.max_contents_per_month,
            "total_contents": quota.total_contents,
            "max_total_contents": plan.max_total_contents,
        }
        return monthly_ok and total_ok, info

    def increment_quota(self, user_id: UUID) -> None:
        """Increment usage counters after a content item is created."""
        quota = self._get_or_create_quota(user_id)
        quota.contents_this_month += 1
        quota.total_contents += 1
        quota.updated_at = datetime.utcnow()
        self.db.commit()

    def create(self, content_data: ContentCreate) -> Content:
        db_content = Content(
            user_id=content_data.user_id,
            source=content_data.source,
            type=content_data.type,
            raw_text=content_data.raw_text,
            url=content_data.url,
            source_platform=content_data.source_platform,
            ingestion_channel=content_data.ingestion_channel or content_data.source,
            external_message_id=content_data.external_message_id,
            external_user_id=content_data.external_user_id,
            sender_name=content_data.sender_name,
            telegram_message_id=content_data.telegram_message_id,
            telegram_chat_id=content_data.telegram_chat_id,
            status=STATUS_QUEUED,
        )
        self.db.add(db_content)
        self.db.commit()
        self.db.refresh(db_content)
        return db_content

    def get_by_id(self, content_id: UUID) -> Optional[Content]:
        return self.db.query(Content).filter(Content.id == content_id).first()

    def get_user_contents(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
        category: Optional[str] = None,
        content_type: Optional[str] = None,
        processed: Optional[bool] = None,
        status: Optional[str] = None,
        ingestion_channel: Optional[str] = None,
        source_platform: Optional[str] = None,
    ) -> tuple[List[Content], int]:
        query = self.db.query(Content).filter(Content.user_id == user_id)

        if category:
            query = query.filter(Content.category == category)
        if content_type:
            query = query.filter(Content.type == content_type)
        if processed is not None:
            query = query.filter(Content.processed == processed)
        if status:
            query = query.filter(Content.status == status)
        if ingestion_channel:
            query = query.filter(Content.ingestion_channel == ingestion_channel)
        if source_platform:
            query = query.filter(Content.source_platform == source_platform)

        total = query.count()
        contents = query.order_by(desc(Content.created_at)).offset(skip).limit(limit).all()

        return contents, total

    # ── Pipeline state transitions ─────────────────────────────────────────

    def mark_processing(self, content_id: UUID) -> None:
        """Called when a worker task starts. Sets status=processing."""
        content = self.get_by_id(content_id)
        if content and content.status not in (STATUS_COMPLETED, STATUS_FAILED):
            content.status = STATUS_PROCESSING
            content.processing_started_at = datetime.utcnow()
            content.updated_at = datetime.utcnow()
            self.db.commit()

    def mark_failed(self, content_id: UUID, error: str) -> None:
        """Called when all retries are exhausted."""
        content = self.get_by_id(content_id)
        if content:
            content.status = STATUS_FAILED
            content.processing_stage = "failed"
            content.processed = True  # prevents re-queuing by webhook
            content.processing_error = error[:500]
            content.updated_at = datetime.utcnow()
            self.db.commit()

    # ── Update after successful AI processing ─────────────────────────────

    def update(self, content_id: UUID, update_data: ContentUpdate) -> Optional[Content]:
        content = self.get_by_id(content_id)
        if not content:
            return None

        for field, value in update_data.model_dump(exclude_unset=True).items():
            setattr(content, field, value)

        content.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(content)
        return content

    def update_processed(
        self,
        content_id: UUID,
        extracted_text: Optional[str] = None,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        importance_score: Optional[int] = None,
        actionable: Optional[bool] = None,
        processing_error: Optional[str] = None,
        transcript: Optional[str] = None,
        transcript_language: Optional[str] = None,
        transcript_confidence: Optional[float] = None,
    ) -> Optional[Content]:
        content = self.get_by_id(content_id)
        if not content:
            return None

        if extracted_text is not None:
            content.extracted_text = extracted_text
        if title is not None:
            content.title = title
        if summary is not None:
            content.summary = summary
        if category is not None:
            content.category = category
        if tags is not None:
            content.tags = tags
        if importance_score is not None:
            content.importance_score = importance_score
        if actionable is not None:
            content.actionable = actionable
        if processing_error is not None:
            content.processing_error = processing_error
        if transcript is not None:
            content.transcript = transcript
        if transcript_language is not None:
            content.transcript_language = transcript_language
        if transcript_confidence is not None:
            content.transcript_confidence = transcript_confidence

        content.processed = True
        content.status = STATUS_COMPLETED
        content.processing_stage = "completed"
        content.processed_at = datetime.utcnow()
        content.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(content)
        return content

    def get_pending_for_batch(
        self, user_id: UUID, max_count: int = 20
    ) -> List[Content]:
        """Return all items not yet processed by any agent, regardless of source platform."""
        return (
            self.db.query(Content)
            .filter(
                Content.user_id == user_id,
                Content.instagram_agent_processed == False,  # noqa: E712
                Content.status.in_(["queued", "failed"]),
            )
            .limit(max_count)
            .all()
        )

    def get_instagram_pending(
        self, user_id: UUID, max_count: int = 20
    ) -> List[Content]:
        """Return Instagram items not yet processed by the agent, excluding in-flight tasks."""
        return (
            self.db.query(Content)
            .filter(
                Content.user_id == user_id,
                Content.source_platform == "instagram",
                Content.instagram_agent_processed == False,  # noqa: E712
                Content.status.in_(["queued", "failed"]),
            )
            .limit(max_count)
            .all()
        )

    def delete(self, content_id: UUID) -> bool:
        content = self.get_by_id(content_id)
        if not content:
            return False

        self.db.delete(content)
        self.db.commit()
        return True

    def create_embedding(self, content_id: UUID, vector: List[float]) -> ContentEmbedding:
        existing = self.db.query(ContentEmbedding).filter(
            ContentEmbedding.content_id == content_id
        ).first()
        if existing:
            self.db.delete(existing)
            self.db.commit()

        embedding = ContentEmbedding(content_id=content_id, vector=vector)
        self.db.add(embedding)
        self.db.commit()
        self.db.refresh(embedding)
        return embedding

    def get_dashboard_stats(self, user_id: UUID) -> dict:
        total = self.db.query(Content).filter(Content.user_id == user_id).count()
        processed = self.db.query(Content).filter(
            Content.user_id == user_id,
            Content.processed == True,
        ).count()
        pending = total - processed

        recent_date = datetime.utcnow() - timedelta(days=7)
        recent = self.db.query(Content).filter(
            Content.user_id == user_id,
            Content.created_at >= recent_date,
        ).count()

        avg_score = self.db.query(func.avg(Content.importance_score)).filter(
            Content.user_id == user_id,
            Content.processed == True,
        ).scalar() or 0

        categories = self.db.query(
            Content.category,
            func.count(Content.id).label("count"),
        ).filter(
            Content.user_id == user_id,
            Content.category.isnot(None),
        ).group_by(Content.category).order_by(desc("count")).limit(5).all()

        # Status breakdown
        status_counts = {}
        for status_val in ("queued", "processing", "completed", "failed"):
            count = self.db.query(Content).filter(
                Content.user_id == user_id,
                Content.status == status_val,
            ).count()
            status_counts[status_val] = count

        return {
            "total_contents": total,
            "processed_contents": processed,
            "pending_contents": pending,
            "recent_contents": recent,
            "average_importance_score": round(float(avg_score), 2),
            "top_categories": [
                {"category": cat, "count": count} for cat, count in categories
            ],
            "status_counts": status_counts,
        }
