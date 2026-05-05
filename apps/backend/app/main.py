import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.api import auth, contents, dashboard, search, webhooks, integrations, instagram, content_batch, workers
from app.api import settings as settings_api

settings = get_settings()

# ── Logging ──────────────────────────────────────────────────────────────────
configure_logging(debug=settings.DEBUG)
logger = structlog.get_logger(__name__)

# ── Sentry ───────────────────────────────────────────────────────────────────
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
    logger.info("Sentry initialised", environment=settings.ENVIRONMENT)

# ── Rate Limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Keepiu API",
    description="Personal intelligent content cataloging platform",
    version="1.0.0",
    debug=settings.DEBUG,
    # Disable /docs and /redoc in production
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Expose limiter on app state so route decorators can reference it
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
# allow_credentials=True requires explicit origins (not "*")
allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(webhooks.router)
app.include_router(contents.router)
app.include_router(dashboard.router)
app.include_router(search.router)
app.include_router(settings_api.router)
app.include_router(integrations.router)
app.include_router(instagram.router)
app.include_router(content_batch.router)
app.include_router(workers.router)


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def _validate_config() -> None:
    default_secret = "signalvault-jwt-secret"
    if settings.JWT_SECRET == default_secret or len(settings.JWT_SECRET) < 32:
        if not settings.DEBUG:
            raise RuntimeError(
                "JWT_SECRET is insecure. Set a strong random secret (≥32 chars) in production."
            )
        logger.warning("JWT_SECRET is using the default/weak value — safe only in development")

    if settings.APP_MODE == "single_user":
        if not settings.APP_PASSWORD:
            raise RuntimeError("APP_MODE=single_user requires APP_PASSWORD to be set.")
        if not settings.SESSION_SECRET:
            raise RuntimeError("APP_MODE=single_user requires SESSION_SECRET to be set.")
        logger.info("Running in single_user mode")

    # Warn loudly when secrets stored in DB would be readable as plaintext
    if not settings.SETTINGS_ENCRYPTION_KEY:
        if not settings.DEBUG:
            raise RuntimeError(
                "SETTINGS_ENCRYPTION_KEY is required in production to encrypt secrets stored in the database. "
                "Generate one with: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        logger.warning(
            "SETTINGS_ENCRYPTION_KEY is not set — secrets stored via the Settings UI will be saved as plaintext. "
            "Set this variable before storing any credentials."
        )


@app.on_event("startup")
async def _bootstrap_single_user_owner() -> None:
    """In single_user mode, ensure the 'owner' account exists."""
    if settings.APP_MODE != "single_user":
        return
    from app.core.database import SessionLocal
    from app.models.user import User as UserModel
    db = SessionLocal()
    try:
        owner = db.query(UserModel).filter(UserModel.username == "owner").first()
        if not owner:
            from app.core.security import get_password_hash
            owner = UserModel(
                username="owner",
                hashed_password=get_password_hash(settings.APP_PASSWORD),
                is_admin=True,
            )
            db.add(owner)
            db.commit()
            logger.info("Created owner account for single_user mode")
        elif not owner.is_admin:
            owner.is_admin = True
            db.commit()
    except Exception as exc:
        logger.error("_bootstrap_single_user_owner failed", error=str(exc))
    finally:
        db.close()


@app.on_event("startup")
async def _bootstrap_admin() -> None:
    """Promote INITIAL_ADMIN_USERNAME to admin on every startup if not already set."""
    if not settings.INITIAL_ADMIN_USERNAME:
        return
    from app.core.database import SessionLocal
    from app.models.user import User as UserModel
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(
            UserModel.username == settings.INITIAL_ADMIN_USERNAME
        ).first()
        if user and not user.is_admin:
            user.is_admin = True
            db.commit()
            logger.info("Promoted user to admin", username=settings.INITIAL_ADMIN_USERNAME)
        elif user:
            logger.info("Admin already set", username=settings.INITIAL_ADMIN_USERNAME)
        else:
            logger.warning(
                "INITIAL_ADMIN_USERNAME not found in DB — create the account first",
                username=settings.INITIAL_ADMIN_USERNAME,
            )
    except Exception as exc:
        logger.error(
            "_bootstrap_admin failed — run 'alembic upgrade head' and restart",
            error=str(exc),
        )
    finally:
        db.close()


@app.on_event("startup")
async def _ensure_setting_defaults() -> None:
    """Insert placeholder rows for all known setting keys so the UI shows them immediately."""
    from app.core.database import SessionLocal
    from app.services.settings_service import SettingsService
    db = SessionLocal()
    try:
        SettingsService(db).ensure_defaults()
    except Exception as exc:
        logger.warning("_ensure_setting_defaults failed", error=str(exc))
    finally:
        db.close()


@app.on_event("startup")
async def _log_integrations() -> None:
    if settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID:
        logger.info(
            "WhatsApp integration enabled",
            phone_number_id=settings.WHATSAPP_PHONE_NUMBER_ID[:6] + "…",
        )
    else:
        logger.warning(
            "WhatsApp integration not configured — set WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID"
        )


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
async def health_check() -> dict:
    from sqlalchemy import text as sa_text
    from app.core.database import SessionLocal

    result: dict = {"status": "healthy", "version": "1.0.0", "mode": settings.APP_MODE}

    # DB probe
    try:
        db = SessionLocal()
        db.execute(sa_text("SELECT 1"))
        db.close()
        result["db"] = "ok"
    except Exception as exc:
        result["db"] = f"error: {exc}"
        result["status"] = "degraded"

    # Redis probe (only if PROCESSING_MODE=worker)
    if settings.PROCESSING_MODE == "worker":
        try:
            import redis as redis_lib
            r = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=2)
            r.ping()
            result["redis"] = "ok"
        except Exception as exc:
            result["redis"] = f"error: {exc}"
            result["status"] = "degraded"
    else:
        result["redis"] = "skipped (inline mode)"

    return result


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {
        "name": "Keepiu API",
        "version": "1.0.0",
        "docs": "/docs" if settings.DEBUG else "disabled in production",
    }
