"""Integrations API — WhatsApp status endpoint."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/whatsapp/status")
async def whatsapp_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Return WhatsApp Business integration configuration status (reads DB first, env fallback)."""
    from app.services.settings_service import SettingsService
    env = get_settings()
    svc = SettingsService(db)

    access_token = svc.get_runtime_value("whatsapp_access_token", env.WHATSAPP_ACCESS_TOKEN)
    phone_number_id = svc.get_runtime_value("whatsapp_phone_number_id", env.WHATSAPP_PHONE_NUMBER_ID)
    verify_token = svc.get_runtime_value("whatsapp_verify_token", env.WHATSAPP_VERIFY_TOKEN)

    configured = bool(access_token and phone_number_id)
    masked_phone_id = None
    if phone_number_id:
        masked_phone_id = phone_number_id[:4] + "…" if len(phone_number_id) > 4 else phone_number_id

    return {
        "configured": configured,
        "phone_number_id": masked_phone_id,
        "verify_token_set": bool(verify_token),
    }
