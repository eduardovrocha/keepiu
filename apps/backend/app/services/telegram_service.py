import logging
import os
import tempfile
from typing import Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _resolve_telegram_token(db: Optional[Session]) -> str:
    if db is not None:
        try:
            from app.services.settings_service import SettingsService
            val = SettingsService(db).get_value("telegram_bot_token")
            if val:
                return val
        except Exception:
            pass
    return settings.TELEGRAM_BOT_TOKEN


class TelegramService:
    def __init__(self, db: Optional[Session] = None) -> None:
        self.token = _resolve_telegram_token(db)
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def download_photo(
        self,
        file_id: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Download a photo from Telegram; return (local_path, error)."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/getFile",
                    params={"file_id": file_id},
                )
                data = response.json()

                if not data.get("ok"):
                    return None, f"Failed to get file info: {data}"

                file_path_api: str = data["result"]["file_path"]
                download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path_api}"

                file_response = await client.get(download_url)
                if file_response.status_code != 200:
                    return None, f"Failed to download file: HTTP {file_response.status_code}"

                suffix = ".png" if ".png" in file_path_api.lower() else ".jpg"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                    f.write(file_response.content)
                    return f.name, None

        except Exception as exc:
            logger.exception("Error downloading photo file_id=%s", file_id)
            return None, str(exc)

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: Optional[int] = None,
    ) -> bool:
        """Send a text message to a Telegram chat."""
        try:
            payload: dict = {"chat_id": chat_id, "text": text}
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/sendMessage",
                    json=payload,
                )
                return response.json().get("ok", False)
        except Exception as exc:
            logger.warning("Failed to send message to chat %s: %s", chat_id, exc)
            return False

    async def set_webhook(self, webhook_url: str) -> bool:
        """Register the webhook URL with Telegram."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/setWebhook",
                    json={"url": webhook_url},
                )
                data = response.json()
                logger.info("Webhook set result: %s", data)
                return data.get("ok", False)
        except Exception as exc:
            logger.error("Error setting webhook: %s", exc)
            return False

    async def delete_webhook(self) -> bool:
        """Remove the currently registered webhook."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{self.base_url}/deleteWebhook")
                return response.json().get("ok", False)
        except Exception as exc:
            logger.error("Error deleting webhook: %s", exc)
            return False
