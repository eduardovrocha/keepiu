from functools import lru_cache
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql://signalvault:signalvault@localhost:5432/signalvault"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_STT_MODEL: str = "gpt-4o-mini-transcribe"

    # Audio transcription limits
    MAX_AUDIO_MINUTES: int = 10

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = ""

    # Security
    JWT_SECRET: str = "signalvault-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24       # legacy — kept for webhook tokens
    JWT_ACCESS_EXPIRATION_MINUTES: int = 15
    JWT_REFRESH_EXPIRATION_DAYS: int = 30
    COOKIE_SECURE: bool = False          # True in production (HTTPS)
    COOKIE_SAMESITE: str = "lax"

    # Registration
    ALLOW_REGISTRATION: bool = True

    # Password reset
    PASSWORD_RESET_EXPIRY_MINUTES: int = 30

    # Content retention (0 = disabled)
    CONTENT_RETENTION_DAYS: int = 0

    # Plans
    DEFAULT_PLAN_NAME: str = "free"

    # App mode — "single_user" (personal vault) | "multi_user" (SaaS)
    APP_MODE: str = "multi_user"
    # Required when APP_MODE=single_user
    APP_PASSWORD: str = ""
    SESSION_SECRET: str = ""

    # Bootstrap: username to auto-promote to admin on startup (set in .env)
    INITIAL_ADMIN_USERNAME: str = ""

    # CORS — comma-separated list for production, e.g. "https://app.example.com"
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    FRONTEND_URL: str = "http://localhost:5173"

    # WhatsApp Business Platform
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_APP_SECRET: str = ""

    # Settings encryption — generate with:
    # python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    SETTINGS_ENCRYPTION_KEY: str = ""

    # Processing mode — "worker" (Celery) | "inline" (background thread, no Redis needed)
    PROCESSING_MODE: str = "worker"

    # Rate Limiting
    WEBHOOK_RATE_LIMIT_PER_MINUTE: int = 60

    # Monitoring
    SENTRY_DSN: Optional[str] = None

    @model_validator(mode="after")
    def _enforce_production_cookie_secure(self) -> "Settings":
        if self.ENVIRONMENT == "production" and not self.COOKIE_SECURE:
            self.COOKIE_SECURE = True
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
