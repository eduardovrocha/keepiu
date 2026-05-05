import logging
import tempfile
import os
from typing import Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_BASE = "https://graph.facebook.com/v18.0"
_MAX_MEDIA_BYTES = 16 * 1024 * 1024  # 16 MB guard


class WhatsAppService:
    def __init__(self, db: Optional[Session] = None) -> None:
        env = get_settings()
        _owned = db is None
        if _owned:
            from app.core.database import SessionLocal
            db = SessionLocal()
        try:
            from app.services.settings_service import SettingsService
            svc = SettingsService(db)
            self.access_token = svc.get_runtime_value("whatsapp_access_token", env.WHATSAPP_ACCESS_TOKEN)
            self.phone_number_id = svc.get_runtime_value("whatsapp_phone_number_id", env.WHATSAPP_PHONE_NUMBER_ID)
        finally:
            if _owned:
                db.close()

    # ── Media ─────────────────────────────────────────────────────────────────

    async def _get_media_info(self, media_id: str) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_BASE}/{media_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            resp.raise_for_status()
            return resp.json()

    async def download_media_bytes(self, media_id: str) -> Tuple[bytes, str]:
        """Download media from WhatsApp and return (bytes, mime_type)."""
        info = await self._get_media_info(media_id)
        media_url: str = info["url"]
        mime_type: str = info.get("mime_type", "application/octet-stream")

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                media_url,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            resp.raise_for_status()

        content = resp.content
        if len(content) > _MAX_MEDIA_BYTES:
            raise ValueError(f"Media too large: {len(content):,} bytes (max {_MAX_MEDIA_BYTES:,})")

        logger.info("WhatsApp media downloaded | media_id=%s size=%d mime=%s", media_id, len(content), mime_type)
        return content, mime_type

    async def download_media_to_file(self, media_id: str) -> Tuple[str, str]:
        """Download media to a temp file and return (path, mime_type)."""
        image_bytes, mime_type = await self.download_media_bytes(media_id)

        ext = ".jpg"
        if "png" in mime_type:
            ext = ".png"
        elif "pdf" in mime_type:
            ext = ".pdf"
        elif "gif" in mime_type:
            ext = ".gif"

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(image_bytes)
            return f.name, mime_type

    # ── Messaging ─────────────────────────────────────────────────────────────

    async def send_text(self, to: str, text: str) -> None:
        """Send a text message reply to a WhatsApp user."""
        if not self.access_token or not self.phone_number_id:
            logger.debug("WhatsApp not configured — skipping send_text to %s", to)
            return

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(
                    f"{_BASE}/{self.phone_number_id}/messages",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "to": to,
                        "type": "text",
                        "text": {"body": text},
                    },
                )
                resp.raise_for_status()
            except Exception:
                logger.warning("Failed to send WhatsApp message to %s", to, exc_info=True)
