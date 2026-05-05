import re
from datetime import datetime
from typing import Optional

from app.services.ingestion.base import NormalizedMessage

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

_SUPPORTED_TYPES = {"text", "image", "document"}


class WhatsAppNormalizer:
    def normalize(self, payload: dict) -> Optional[NormalizedMessage]:
        try:
            entry = payload.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})

            if value.get("messaging_product") != "whatsapp":
                return None

            messages = value.get("messages", [])
            if not messages:
                return None  # status update, not an inbound message

            msg = messages[0]
            msg_type = msg.get("type", "")

            if msg_type not in _SUPPORTED_TYPES:
                return None  # audio, video, reaction, etc. — out of scope

            wa_id: str = msg.get("from", "")
            wamid: str = msg.get("id", "")
            timestamp: Optional[str] = msg.get("timestamp")

            if not wa_id or not wamid:
                return None

            contacts = value.get("contacts", [])
            contact = next((c for c in contacts if c.get("wa_id") == wa_id), {})
            sender_name = contact.get("profile", {}).get("name")

            content_type = "text"
            text: Optional[str] = None
            url: Optional[str] = None
            media_id: Optional[str] = None
            media_mime_type: Optional[str] = None

            if msg_type == "text":
                raw: str = msg.get("text", {}).get("body", "")
                if not raw:
                    return None
                m = _URL_RE.search(raw)
                if m:
                    content_type = "link"
                    url = m.group(0)
                text = raw

            elif msg_type == "image":
                content_type = "image"
                img = msg.get("image", {})
                media_id = img.get("id")
                media_mime_type = img.get("mime_type", "image/jpeg")
                text = img.get("caption") or None

            elif msg_type == "document":
                content_type = "file"
                doc = msg.get("document", {})
                media_id = doc.get("id")
                media_mime_type = doc.get("mime_type", "application/octet-stream")
                text = doc.get("caption") or doc.get("filename") or None

            received_at = (
                datetime.utcfromtimestamp(int(timestamp)) if timestamp else datetime.utcnow()
            )

            return NormalizedMessage(
                channel="whatsapp",
                external_message_id=wamid,
                external_user_id=wa_id,
                sender_name=sender_name,
                text=text,
                content_type=content_type,
                url=url,
                media_id=media_id,
                media_mime_type=media_mime_type,
                received_at=received_at,
                raw_payload=payload,
                channel_metadata={"phone_number_id": value.get("metadata", {}).get("phone_number_id")},
            )

        except (KeyError, IndexError, ValueError):
            return None
