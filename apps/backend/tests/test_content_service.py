"""Unit tests for ContentService."""
import uuid
import pytest

from app.models.content import Content
from app.schemas.content import ContentCreate, ContentUpdate
from app.services.content_service import ContentService


def _make_content(user_id, type_="text", raw_text="hello world", **kwargs):
    return ContentCreate(
        user_id=user_id,
        source="telegram",
        type=type_,
        raw_text=raw_text,
        **kwargs,
    )


class TestContentServiceCreate:
    def test_create_returns_content_with_id(self, db_session, sample_user):
        svc = ContentService(db_session)
        data = _make_content(sample_user.id)
        content = svc.create(data)

        assert content.id is not None
        assert content.type == "text"
        assert content.raw_text == "hello world"
        assert content.user_id == sample_user.id
        assert content.processed is False

    def test_create_link_preserves_url(self, db_session, sample_user):
        svc = ContentService(db_session)
        data = _make_content(sample_user.id, type_="link", url="https://example.com")
        content = svc.create(data)

        assert content.url == "https://example.com"


class TestContentServiceRead:
    def test_get_by_id_returns_content(self, db_session, sample_user):
        svc = ContentService(db_session)
        content = svc.create(_make_content(sample_user.id))
        fetched = svc.get_by_id(content.id)

        assert fetched is not None
        assert fetched.id == content.id

    def test_get_by_id_missing_returns_none(self, db_session):
        svc = ContentService(db_session)
        result = svc.get_by_id(uuid.uuid4())
        assert result is None

    def test_get_user_contents_filters_by_user(self, db_session, sample_user):
        from app.models.user import User
        from app.core.security import get_password_hash

        other_user = User(
            id=uuid.uuid4(),
            username="otheruser",
            hashed_password=get_password_hash("x"),
        )
        db_session.add(other_user)
        db_session.commit()

        svc = ContentService(db_session)
        svc.create(_make_content(sample_user.id, raw_text="mine"))
        svc.create(_make_content(other_user.id, raw_text="not mine"))

        results, total = svc.get_user_contents(user_id=sample_user.id)
        assert total == 1
        assert results[0].raw_text == "mine"

    def test_get_user_contents_filter_by_type(self, db_session, sample_user):
        svc = ContentService(db_session)
        svc.create(_make_content(sample_user.id, type_="text"))
        svc.create(_make_content(sample_user.id, type_="link", url="https://x.com"))

        results, total = svc.get_user_contents(user_id=sample_user.id, content_type="link")
        assert total == 1
        assert results[0].type == "link"

    def test_get_user_contents_pagination(self, db_session, sample_user):
        svc = ContentService(db_session)
        for i in range(5):
            svc.create(_make_content(sample_user.id, raw_text=f"item {i}"))

        page1, total = svc.get_user_contents(user_id=sample_user.id, skip=0, limit=3)
        assert len(page1) == 3
        assert total == 5


class TestContentServiceUpdate:
    def test_update_processed_sets_fields(self, db_session, sample_user):
        svc = ContentService(db_session)
        content = svc.create(_make_content(sample_user.id))

        updated = svc.update_processed(
            content_id=content.id,
            title="My Title",
            summary="My Summary",
            category="IA",
            tags=["ai", "ml"],
            importance_score=8,
            actionable=True,
        )

        assert updated.processed is True
        assert updated.title == "My Title"
        assert updated.category == "IA"
        assert updated.importance_score == 8
        assert updated.actionable is True

    def test_update_processed_missing_content_returns_none(self, db_session):
        svc = ContentService(db_session)
        result = svc.update_processed(content_id=uuid.uuid4(), title="x")
        assert result is None


class TestContentServiceDelete:
    def test_delete_removes_content(self, db_session, sample_user):
        svc = ContentService(db_session)
        content = svc.create(_make_content(sample_user.id))

        assert svc.delete(content.id) is True
        assert svc.get_by_id(content.id) is None

    def test_delete_missing_returns_false(self, db_session):
        svc = ContentService(db_session)
        assert svc.delete(uuid.uuid4()) is False


class TestDashboardStats:
    def test_stats_empty_user(self, db_session, sample_user):
        svc = ContentService(db_session)
        stats = svc.get_dashboard_stats(sample_user.id)

        assert stats["total_contents"] == 0
        assert stats["pending_contents"] == 0
        assert stats["processed_contents"] == 0
        assert stats["top_categories"] == []

    def test_stats_counts_processed(self, db_session, sample_user):
        svc = ContentService(db_session)
        c1 = svc.create(_make_content(sample_user.id))
        svc.update_processed(content_id=c1.id, title="done", category="IA")
        svc.create(_make_content(sample_user.id))  # unprocessed

        stats = svc.get_dashboard_stats(sample_user.id)
        assert stats["total_contents"] == 2
        assert stats["processed_contents"] == 1
        assert stats["pending_contents"] == 1
