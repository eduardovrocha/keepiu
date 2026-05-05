from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class NormalizedMessage:
    """Unified message representation across all ingestion channels."""

    channel: str                     # "telegram" | "whatsapp"
    external_message_id: str        # Telegram message_id (as str) or WhatsApp wamid
    external_user_id: str           # Telegram user_id (as str) or WhatsApp phone (wa_id)
    sender_name: Optional[str]      # Display name from the channel

    text: Optional[str]             # Message text content
    content_type: str               # "text" | "image" | "link" | "file" | "forward"
    url: Optional[str]              # Extracted URL for link-type messages
    media_id: Optional[str]         # Telegram file_id or WhatsApp media_id
    media_mime_type: Optional[str]  # MIME type for media messages

    received_at: datetime
    raw_payload: dict = field(default_factory=dict)
    channel_metadata: dict = field(default_factory=dict)
