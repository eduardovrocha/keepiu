import re
from datetime import datetime
from typing import Optional

from app.services.ingestion.base import NormalizedMessage

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


class TelegramNormalizer:
    def normalize(self, payload: dict) -> Optional[NormalizedMessage]:
        message = payload.get("message")
        if not message:
            return None

        from_user = message.get("from", {})
        telegram_id = from_user.get("id")
        if not telegram_id:
            return None

        first = from_user.get("first_name", "")
        last = from_user.get("last_name", "")
        sender_name = f"{first} {last}".strip() or None

        message_id: Optional[int] = message.get("message_id")
        chat_id: Optional[int] = message.get("chat", {}).get("id")

        content_type = "text"
        text: Optional[str] = None
        url: Optional[str] = None
        media_id: Optional[str] = None
        media_mime_type: Optional[str] = None

        if message.get("photo"):
            content_type = "image"
            photos = message["photo"]
            largest = max(photos, key=lambda p: p.get("file_size", 0))
            media_id = largest.get("file_id")
            media_mime_type = "image/jpeg"
            text = message.get("caption") or None

        elif message.get("text"):
            raw: str = message["text"]
            if raw.startswith("/"):
                return None  # bot command — not content
            m = _URL_RE.search(raw)
            if m:
                content_type = "link"
                url = m.group(0)
            text = raw

        elif message.get("forward_from") or message.get("forward_sender_name"):
            raw = message.get("text", "") or ""
            content_type = "forward"
            m = _URL_RE.search(raw)
            if m:
                content_type = "link"
                url = m.group(0)
            text = raw or None

        else:
            return None  # unsupported message type

        return NormalizedMessage(
            channel="telegram",
            external_message_id=str(message_id) if message_id else "",
            external_user_id=str(telegram_id),
            sender_name=sender_name,
            text=text,
            content_type=content_type,
            url=url,
            media_id=media_id,
            media_mime_type=media_mime_type,
            received_at=datetime.utcnow(),
            raw_payload=payload,
            channel_metadata={
                "telegram_message_id": message_id,
                "telegram_chat_id": chat_id,
            },
        )
