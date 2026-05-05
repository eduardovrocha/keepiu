import hashlib
import hmac
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Header, Query, status
from fastapi.responses import PlainTextResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.services.user_service import UserService
from app.services.content_service import ContentService
from app.services.ingestion import get_normalizer, NormalizedMessage
from app.schemas.content import ContentCreate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)


# ── Shared ingestion pipeline ─────────────────────────────────────────────────

async def _ingest(normalized: NormalizedMessage, db: Session) -> dict:
    """Create a Content record from a normalized message and queue the right task."""
    user_service = UserService(db)
    channel = normalized.channel

    if channel == "telegram":
        user = user_service.get_or_create(
            telegram_id=int(normalized.external_user_id),
            name=normalized.sender_name,
        )
    elif channel == "whatsapp":
        user = user_service.get_or_create_whatsapp(
            phone=normalized.external_user_id,
            name=normalized.sender_name,
        )
    else:
        raise ValueError(f"Unknown channel: {channel!r}")

    # Detect source platform from URL before creating the record
    source_platform: Optional[str] = None
    if normalized.content_type == "link" and normalized.url:
        from app.services.source_detector import detect_source
        detected = detect_source(normalized.url)
        if detected != "unknown":
            source_platform = detected

    meta = normalized.channel_metadata
    content_data = ContentCreate(
        user_id=user.id,
        source=channel,
        type=normalized.content_type,
        raw_text=normalized.text,
        url=normalized.url,
        source_platform=source_platform,
        ingestion_channel=channel,
        external_message_id=normalized.external_message_id,
        external_user_id=normalized.external_user_id,
        sender_name=normalized.sender_name,
        telegram_message_id=meta.get("telegram_message_id"),
        telegram_chat_id=meta.get("telegram_chat_id"),
    )
    content_service = ContentService(db)
    content = content_service.create(content_data)

    # ── Route to the right task (Celery or inline) ───────────────────────────
    from app.core.processing import route_task
    from app.workers.content_processor import process_content_task, process_image_task

    if normalized.content_type == "image" and normalized.media_id:
        if channel == "telegram":
            route_task(process_image_task, str(content.id), normalized.media_id)
        else:
            from app.workers.whatsapp_tasks import process_whatsapp_image_task
            route_task(process_whatsapp_image_task, str(content.id), normalized.media_id)
    elif source_platform == "instagram":
        from app.workers.instagram_tasks import process_instagram_task
        route_task(process_instagram_task, str(content.id))
    else:
        route_task(process_content_task, str(content.id))

    return {"ok": True, "content_id": str(content.id), "type": normalized.content_type}


# ── Telegram ──────────────────────────────────────────────────────────────────

@router.post("/telegram")
@limiter.limit(f"{settings.WEBHOOK_RATE_LIMIT_PER_MINUTE}/minute")
async def telegram_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
) -> dict:
    from app.services.settings_service import SettingsService
    effective_secret = SettingsService(db).get_runtime_value(
        "telegram_webhook_secret", settings.TELEGRAM_WEBHOOK_SECRET
    )
    if effective_secret and x_telegram_bot_api_secret_token != effective_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret token")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    normalizer = get_normalizer("telegram")
    normalized = normalizer.normalize(payload)

    if normalized is None:
        return {"ok": True, "ignored": True}

    chat_id = normalized.channel_metadata.get("telegram_chat_id")
    message_id = normalized.channel_metadata.get("telegram_message_id")

    # Command dispatch — handle bot commands before ingestion
    if normalized.text:
        from app.services.ingestion.telegram_dispatcher import dispatch as tg_dispatch
        reply = await tg_dispatch(normalized.text, chat_id, db)
        if reply is not None:
            if chat_id:
                try:
                    from app.services.telegram_service import TelegramService
                    await TelegramService().send_message(
                        chat_id=chat_id,
                        text=reply,
                        reply_to_message_id=message_id,
                    )
                except Exception:
                    logger.warning("Failed to send Telegram command reply to chat %s", chat_id)
            return {"ok": True, "command": True}

    result = await _ingest(normalized, db)

    # Acknowledge receipt
    if chat_id:
        try:
            from app.services.telegram_service import TelegramService
            await TelegramService().send_message(
                chat_id=chat_id,
                text="✅ Recebido! Processando com IA...",
                reply_to_message_id=message_id,
            )
        except Exception:
            logger.warning("Failed to send Telegram confirmation to chat %s", chat_id)

    logger.info(
        "Telegram webhook: content=%s type=%s user=%s",
        result["content_id"], result["type"], normalized.external_user_id,
    )
    return result


# ── WhatsApp ──────────────────────────────────────────────────────────────────

@router.get("/whatsapp")
async def whatsapp_verify(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    """Meta webhook verification handshake."""
    if hub_mode != "subscribe":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid hub.mode")

    from app.services.settings_service import SettingsService
    verify_token = SettingsService(db).get_runtime_value(
        "whatsapp_verify_token", settings.WHATSAPP_VERIFY_TOKEN
    )
    if not verify_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp not configured",
        )

    if hub_verify_token != verify_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token mismatch")

    return PlainTextResponse(content=hub_challenge)


_MAX_WEBHOOK_BODY = 5 * 1024 * 1024  # 5 MB


@router.post("/whatsapp")
@limiter.limit(f"{settings.WEBHOOK_RATE_LIMIT_PER_MINUTE}/minute")
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(None),
) -> dict:
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_WEBHOOK_BODY:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Payload too large")

    body_bytes = await request.body()
    if len(body_bytes) > _MAX_WEBHOOK_BODY:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Payload too large")

    # Validate HMAC-SHA256 signature using DB value (with env fallback)
    from app.services.settings_service import SettingsService
    app_secret = SettingsService(db).get_runtime_value(
        "whatsapp_app_secret", settings.WHATSAPP_APP_SECRET
    )
    if app_secret:
        sig = hmac.new(
            app_secret.encode(),
            body_bytes,
            hashlib.sha256,
        ).hexdigest()
        expected = f"sha256={sig}"
        if not x_hub_signature_256 or not hmac.compare_digest(expected, x_hub_signature_256):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
    elif not settings.DEBUG:
        # In production, reject requests without a configured app_secret to prevent spoofing
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp app_secret not configured — set it in Settings to enable webhook validation",
        )

    try:
        import json
        payload = json.loads(body_bytes)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    normalizer = get_normalizer("whatsapp")
    normalized = normalizer.normalize(payload)

    if normalized is None:
        # Status updates, read receipts, etc. — acknowledge but don't process
        return {"ok": True, "ignored": True}

    # Command dispatch — handle bot commands before ingestion
    if normalized.text:
        from app.services.ingestion.whatsapp_dispatcher import dispatch as wa_dispatch
        reply = await wa_dispatch(normalized.text, normalized.external_user_id, db)
        if reply is not None:
            try:
                from app.services.whatsapp_service import WhatsAppService
                await WhatsAppService(db).send_text(to=normalized.external_user_id, text=reply)
            except Exception:
                logger.warning("Failed to send WhatsApp command reply to %s", normalized.external_user_id)
            return {"ok": True, "command": True}

    result = await _ingest(normalized, db)

    # Send confirmation back via WhatsApp
    try:
        from app.services.whatsapp_service import WhatsAppService
        await WhatsAppService(db).send_text(
            to=normalized.external_user_id,
            text="✅ Recebido! Processando com IA...",
        )
    except Exception:
        logger.warning("Failed to send WhatsApp confirmation to %s", normalized.external_user_id)

    logger.info(
        "WhatsApp webhook: content=%s type=%s user=%s",
        result["content_id"], result["type"], normalized.external_user_id,
    )
    return result
