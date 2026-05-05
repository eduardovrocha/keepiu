import logging
from datetime import datetime
from typing import Optional, List, Dict
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models.system_setting import SystemSetting
from app.schemas.settings import SettingResponse, SettingUpdate, CheckResult, TestSettingsResponse

logger = logging.getLogger(__name__)

# All managed keys and their metadata
SETTING_DEFINITIONS: dict[str, dict] = {
    "telegram_bot_url": {
        "is_secret": False,
        "env_key": None,
    },
    "openai_api_key": {
        "is_secret": True,
        "env_key": "OPENAI_API_KEY",
    },
    "telegram_bot_token": {
        "is_secret": True,
        "env_key": "TELEGRAM_BOT_TOKEN",
    },
    "telegram_webhook_secret": {
        "is_secret": True,
        "env_key": "TELEGRAM_WEBHOOK_SECRET",
    },
    "whatsapp_access_token": {
        "is_secret": True,
        "env_key": "WHATSAPP_ACCESS_TOKEN",
    },
    "whatsapp_phone_number_id": {
        "is_secret": False,
        "env_key": "WHATSAPP_PHONE_NUMBER_ID",
    },
    "whatsapp_verify_token": {
        "is_secret": True,
        "env_key": "WHATSAPP_VERIFY_TOKEN",
    },
    "whatsapp_app_secret": {
        "is_secret": True,
        "env_key": "WHATSAPP_APP_SECRET",
    },
    "audio_transcription_enabled": {
        "is_secret": False,
        "env_key": None,
    },
}


def _mask(key: str, value: str) -> str:
    """Return a masked representation of a secret value."""
    if not value:
        return ""
    tail = value[-4:] if len(value) >= 4 else value
    if key == "openai_api_key":
        # sk-****xxxx
        prefix = "sk-" if value.startswith("sk-") else value[:3]
        return f"{prefix}****{tail}"
    if key == "telegram_bot_token":
        # Telegram tokens are "{bot_id}:{token}" — show the bot_id part
        parts = value.split(":", 1)
        if len(parts) == 2:
            return f"{parts[0]}:****{tail}"
        return f"****{tail}"
    # Default: only tail
    return f"****{tail}"


class SettingsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Encryption helpers ────────────────────────────────────────────────────

    def _enc_key(self) -> str:
        from app.core.config import get_settings
        return get_settings().SETTINGS_ENCRYPTION_KEY

    def _encrypt(self, value: str) -> str:
        key = self._enc_key()
        if not key:
            return value
        from app.core.security import encrypt_setting
        return encrypt_setting(value, key)

    def _decrypt(self, value: str) -> str:
        key = self._enc_key()
        if not key:
            return value
        from app.core.security import decrypt_setting
        return decrypt_setting(value, key)

    def _get_row(self, key: str) -> Optional[SystemSetting]:
        return (
            self.db.query(SystemSetting).filter(SystemSetting.key == key).first()
        )

    def ensure_defaults(self) -> None:
        """Insert rows for every known key if they don't exist yet."""
        for key, meta in SETTING_DEFINITIONS.items():
            if not self._get_row(key):
                row = SystemSetting(key=key, is_secret=meta["is_secret"])
                self.db.add(row)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()

    def get_all(self) -> List[SettingResponse]:
        rows = self.db.query(SystemSetting).order_by(SystemSetting.key).all()
        result = []
        for row in rows:
            if row.key not in SETTING_DEFINITIONS:
                continue
            result.append(self._to_response(row))
        return result

    def get_value(self, key: str) -> Optional[str]:
        """Return the decrypted stored value. Returns None if not set."""
        row = self._get_row(key)
        if not row or not row.value:
            return None
        meta = SETTING_DEFINITIONS.get(key)
        if meta and meta["is_secret"]:
            return self._decrypt(row.value)
        return row.value

    def get_bool_value(self, key: str, default: bool = False) -> bool:
        """Return the stored value parsed as a boolean."""
        val = self.get_value(key)
        if val is None:
            return default
        return val.strip().lower() in ("true", "1", "yes")

    def get_runtime_value(self, key: str, env_fallback: str = "") -> str:
        """Return DB value (decrypted) if set, otherwise the provided env fallback."""
        db_val = self.get_value(key)
        return db_val if db_val else env_fallback

    def set_value(self, key: str, value: str) -> SettingResponse:
        meta = SETTING_DEFINITIONS.get(key)
        if meta is None:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown setting key: {key}",
            )
        stored = self._encrypt(value) if meta["is_secret"] else value
        row = self._get_row(key)
        if row:
            row.value = stored
            row.updated_at = datetime.utcnow()
        else:
            row = SystemSetting(key=key, value=stored, is_secret=meta["is_secret"])
            self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._to_response(row)

    def batch_update(self, updates: List[SettingUpdate]) -> List[SettingResponse]:
        results = []
        for update in updates:
            results.append(self.set_value(update.key, update.value))
        return results

    def reveal(self, key: str) -> Optional[str]:
        """Return the plain (decrypted) value for a key."""
        return self.get_value(key)

    def reveal_all(self) -> Dict[str, Optional[str]]:
        """Return plain (decrypted) values for every known setting (None if not set)."""
        rows = self.db.query(SystemSetting).all()
        result: Dict[str, Optional[str]] = {}
        for row in rows:
            if row.key in SETTING_DEFINITIONS:
                meta = SETTING_DEFINITIONS[row.key]
                if meta["is_secret"] and row.value:
                    result[row.key] = self._decrypt(row.value)
                else:
                    result[row.key] = row.value
        return result

    def test_connectivity(self) -> TestSettingsResponse:
        """Validate all credentials by calling external APIs. No secrets in response."""
        from app.core.config import get_settings
        env = get_settings()
        checks: Dict[str, CheckResult] = {}

        # ── 1. OpenAI ────────────────────────────────────────────────────────
        openai_key = self.get_runtime_value("openai_api_key", env.OPENAI_API_KEY)
        if not openai_key:
            checks["openai"] = CheckResult(ok=False, message="API key not configured")
        else:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key, timeout=10.0)
                client.models.list()
                checks["openai"] = CheckResult(ok=True, message="Connected successfully")
            except Exception as exc:
                checks["openai"] = CheckResult(ok=False, message=f"Connection failed: {str(exc)[:120]}")

        # ── 2. Telegram Bot Token ─────────────────────────────────────────────
        token = self.get_runtime_value("telegram_bot_token", env.TELEGRAM_BOT_TOKEN)
        if not token:
            checks["telegram"] = CheckResult(ok=False, message="Bot token not configured")
        else:
            try:
                import httpx
                with httpx.Client(timeout=8.0) as client:
                    resp = client.get(f"https://api.telegram.org/bot{token}/getMe")
                    data = resp.json()
                    if data.get("ok"):
                        username = data["result"].get("username", "")
                        checks["telegram"] = CheckResult(
                            ok=True,
                            message=f"Bot @{username} is valid",
                        )
                    else:
                        desc = data.get("description", "Invalid token")
                        checks["telegram"] = CheckResult(ok=False, message=desc)
            except Exception as exc:
                checks["telegram"] = CheckResult(ok=False, message=f"Request failed: {str(exc)[:120]}")

        # ── 3. Webhook Secret ─────────────────────────────────────────────────
        secret = self.get_runtime_value("telegram_webhook_secret", env.TELEGRAM_WEBHOOK_SECRET)
        if not secret:
            checks["webhook_secret"] = CheckResult(ok=False, message="Not configured")
        elif len(secret) < 16:
            checks["webhook_secret"] = CheckResult(
                ok=False,
                message=f"Too short — {len(secret)} chars (minimum 16)",
            )
        else:
            checks["webhook_secret"] = CheckResult(
                ok=True,
                message=f"Valid — {len(secret)} characters",
            )

        # ── 4. Bot URL ────────────────────────────────────────────────────────
        bot_url = self.get_value("telegram_bot_url")
        if not bot_url:
            checks["bot_url"] = CheckResult(ok=False, message="Not configured")
        else:
            try:
                parsed = urlparse(bot_url)
                if parsed.scheme in ("http", "https") and parsed.netloc:
                    checks["bot_url"] = CheckResult(ok=True, message=f"Valid URL")
                else:
                    checks["bot_url"] = CheckResult(ok=False, message="Invalid URL format")
            except Exception:
                checks["bot_url"] = CheckResult(ok=False, message="Invalid URL")

        overall = all(c.ok for c in checks.values())
        return TestSettingsResponse(overall=overall, checks=checks)

    def _to_response(self, row: SystemSetting) -> SettingResponse:
        has_value = bool(row.value)
        if row.is_secret and has_value:
            plain = self._decrypt(row.value)
            display = _mask(row.key, plain)
        else:
            display = row.value
        return SettingResponse(
            key=row.key,
            display_value=display,
            is_secret=row.is_secret,
            has_value=has_value,
            updated_at=row.updated_at,
        )
