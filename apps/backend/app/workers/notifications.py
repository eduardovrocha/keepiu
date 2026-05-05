"""Bot notification helpers for Celery workers.

Both _send_completion_notification and _send_failure_notification are
best-effort: they never raise, so a notification failure never masks
the original task result.
"""
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


def send_completion(content: Any, title: str | None) -> None:
    """Notify the user via the originating bot channel that processing succeeded."""
    try:
        channel = content.ingestion_channel
        label = title or (content.raw_text or "")
        label = label[:80] + ("…" if len(label) > 80 else "")
        msg = f"✅ Processado: {label}" if label else "✅ Conteúdo processado com sucesso!"
        _dispatch(content, channel, msg)
    except Exception:
        logger.warning("send_completion failed for content %s", getattr(content, "id", "?"))


def send_failure(content: Any, reason: str = "") -> None:
    """Notify the user via the originating bot channel that processing permanently failed."""
    try:
        channel = content.ingestion_channel
        detail = f": {reason[:100]}" if reason else ""
        msg = f"❌ Falha no processamento{detail}\n\nVocê pode tentar reprocessar pelo painel."
        _dispatch(content, channel, msg)
    except Exception:
        logger.warning("send_failure notification failed for content %s", getattr(content, "id", "?"))


def _dispatch(content: Any, channel: str | None, msg: str) -> None:
    if channel == "telegram" and content.telegram_chat_id:
        from app.services.telegram_service import TelegramService
        asyncio.run(TelegramService().send_message(
            chat_id=content.telegram_chat_id,
            text=msg,
            reply_to_message_id=content.telegram_message_id,
        ))
    elif channel == "whatsapp" and content.external_user_id:
        from app.services.whatsapp_service import WhatsAppService
        asyncio.run(WhatsAppService().send_text(to=content.external_user_id, text=msg))
