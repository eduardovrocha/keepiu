"""Unit tests for the Telegram webhook handler."""
from unittest.mock import patch, AsyncMock, MagicMock
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.core.config import get_settings


# ── In-memory DB setup ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="module")
def client(test_engine):
    SessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _telegram_payload(text: str = "Hello world", telegram_id: int = 123456):
    return {
        "message": {
            "message_id": 1,
            "from": {"id": telegram_id, "first_name": "Test"},
            "chat": {"id": telegram_id},
            "text": text,
        }
    }


SETTINGS = get_settings()
WEBHOOK_HEADERS = {"X-Telegram-Bot-Api-Secret-Token": SETTINGS.TELEGRAM_WEBHOOK_SECRET or ""}


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestWebhookAuth:
    def test_wrong_secret_returns_401(self, client):
        response = client.post(
            "/webhooks/telegram",
            json=_telegram_payload(),
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        )
        # Only enforced when TELEGRAM_WEBHOOK_SECRET is set
        if SETTINGS.TELEGRAM_WEBHOOK_SECRET:
            assert response.status_code == 401

    def test_invalid_json_returns_400(self, client):
        response = client.post(
            "/webhooks/telegram",
            content="not-json",
            headers={**WEBHOOK_HEADERS, "Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_empty_update_ignored(self, client):
        with patch("app.api.webhooks.process_content_task") as mock_task:
            response = client.post(
                "/webhooks/telegram",
                json={"update_id": 1},
                headers=WEBHOOK_HEADERS,
            )
        assert response.status_code == 200
        assert response.json()["ignored"] is True
        mock_task.delay.assert_not_called()


class TestWebhookProcessing:
    def test_text_message_creates_content_and_queues(self, client):
        with (
            patch("app.api.webhooks.process_content_task") as mock_task,
            patch("app.api.webhooks.TelegramService") as mock_svc_cls,
        ):
            mock_svc = AsyncMock()
            mock_svc.send_message.return_value = True
            mock_svc_cls.return_value = mock_svc

            response = client.post(
                "/webhooks/telegram",
                json=_telegram_payload("This is a test message"),
                headers=WEBHOOK_HEADERS,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["queued"] is True
        assert body["type"] == "text"
        mock_task.delay.assert_called_once()

    def test_link_message_detected_as_link(self, client):
        with (
            patch("app.api.webhooks.process_content_task") as mock_task,
            patch("app.api.webhooks.TelegramService") as mock_svc_cls,
        ):
            mock_svc = AsyncMock()
            mock_svc_cls.return_value = mock_svc

            response = client.post(
                "/webhooks/telegram",
                json=_telegram_payload("Check https://example.com for details"),
                headers=WEBHOOK_HEADERS,
            )

        assert response.status_code == 200
        assert response.json()["type"] == "link"

    def test_image_message_queues_image_task(self, client):
        payload = {
            "message": {
                "message_id": 2,
                "from": {"id": 789, "first_name": "Img"},
                "chat": {"id": 789},
                "photo": [
                    {"file_id": "small_id", "file_size": 100},
                    {"file_id": "large_id", "file_size": 5000},
                ],
            }
        }
        with (
            patch("app.api.webhooks.process_image_task") as mock_img,
            patch("app.api.webhooks.TelegramService") as mock_svc_cls,
        ):
            mock_svc = AsyncMock()
            mock_svc_cls.return_value = mock_svc

            response = client.post(
                "/webhooks/telegram",
                json=payload,
                headers=WEBHOOK_HEADERS,
            )

        assert response.status_code == 200
        assert response.json()["type"] == "image"
        mock_img.delay.assert_called_once()
        # Should pick the largest photo (file_id="large_id")
        args = mock_img.delay.call_args[0]
        assert args[1] == "large_id"
