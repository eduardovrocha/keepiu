import logging
import secrets as _secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request, Response, status, Depends
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import (
    create_access_token, create_refresh_token, hash_token,
    verify_password, get_password_hash,
)
from app.core.session import sign_session, SESSION_COOKIE, SESSION_MAX_AGE
from app.core.config import get_settings
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.password_reset_token import PasswordResetToken
from app.schemas.user import UserRegisterRequest, UserRegisterResponse, LinkTelegramRequest
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

_ACCESS_COOKIE = "access_token"
_REFRESH_COOKIE = "refresh_token"


# ── Cookie helpers ─────────────────────────────────────────────────────────────

def _set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_ACCESS_COOKIE,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.JWT_ACCESS_EXPIRATION_MINUTES * 60,
        path="/",
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.JWT_REFRESH_EXPIRATION_DAYS * 86400,
        path="/auth",  # covers /auth/refresh and /auth/logout
    )


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(key=_ACCESS_COOKIE, path="/")
    response.delete_cookie(key=_REFRESH_COOKIE, path="/auth")


def _issue_tokens(response: Response, user: User, db: Session) -> None:
    """Create access + refresh tokens, set cookies, persist refresh token hash."""
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username},
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_EXPIRATION_MINUTES),
    )
    raw_refresh, refresh_hash = create_refresh_token()
    expires_at = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_EXPIRATION_DAYS)

    db_token = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=expires_at,
    )
    db.add(db_token)
    db.commit()

    _set_access_cookie(response, access_token)
    _set_refresh_cookie(response, raw_refresh)


# ── Schemas ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: str
    username: str
    name: str | None = None
    telegram_id: int | None = None
    is_admin: bool = False


class ForgotPasswordRequest(BaseModel):
    username: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/config")
async def auth_config() -> dict:
    """Return public auth configuration (mode only — no secrets)."""
    return {"mode": settings.APP_MODE}


@router.post("/register", response_model=UserRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db),
) -> UserRegisterResponse:
    """Register a new user with username and password."""
    if settings.APP_MODE == "single_user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled in single-user mode",
        )
    if not settings.ALLOW_REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is currently closed",
        )

    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    if request.email:
        existing_email = db.query(User).filter(User.email == request.email).first()
        if existing_email:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        username=request.username,
        email=request.email,
        hashed_password=get_password_hash(request.password),
        telegram_id=request.telegram_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserRegisterResponse.model_validate(user)


@router.post("/login", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Authenticate and set httpOnly session/token cookies.

    In single_user mode: validates password against APP_PASSWORD, sets HMAC session cookie.
    In multi_user mode: validates username+password, sets JWT access+refresh cookies.
    """
    if settings.APP_MODE == "single_user":
        if not settings.APP_PASSWORD or not settings.SESSION_SECRET:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Single-user mode not configured (APP_PASSWORD or SESSION_SECRET missing)",
            )
        if not _secrets.compare_digest(body.password, settings.APP_PASSWORD):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        user = db.query(User).filter(User.username == "owner").first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Owner account not found — restart the server to bootstrap it",
            )

        token = sign_session(str(user.id), settings.SESSION_SECRET)
        response.set_cookie(
            key=SESSION_COOKIE,
            value=token,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            max_age=SESSION_MAX_AGE,
            path="/",
        )
        return {"authenticated": True, "is_admin": True}

    # multi_user mode — username + password + JWT cookies
    user = db.query(User).filter(User.username == body.username).first()

    if not user or not user.hashed_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    _issue_tokens(response, user, db)
    return {"authenticated": True, "is_admin": user.is_admin}


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    """Exchange a valid refresh token cookie for new access + refresh tokens (rotation)."""
    raw_refresh = request.cookies.get(_REFRESH_COOKIE)
    if not raw_refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    token_hash = hash_token(raw_refresh)
    db_token = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,  # noqa: E712
            RefreshToken.expires_at > datetime.utcnow(),
        )
        .first()
    )

    if not db_token:
        _clear_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user:
        _clear_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Revoke the used token (rotation)
    db_token.revoked = True
    db.commit()

    _issue_tokens(response, user, db)
    return {"refreshed": True}


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    """Revoke refresh token / session cookie and clear all auth cookies."""
    if settings.APP_MODE == "single_user":
        response.delete_cookie(key=SESSION_COOKIE, path="/")
        return {"logged_out": True}

    raw_refresh = request.cookies.get(_REFRESH_COOKIE)
    if raw_refresh:
        token_hash = hash_token(raw_refresh)
        db_token = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        if db_token:
            db_token.revoked = True
            db.commit()

    _clear_cookies(response)
    return {"logged_out": True}


@router.get("/me", response_model=UserInfo)
async def get_me(current_user: User = Depends(get_current_user)) -> UserInfo:
    """Return current authenticated user info."""
    return UserInfo(
        id=str(current_user.id),
        username=current_user.username or "",
        name=current_user.name,
        telegram_id=current_user.telegram_id,
        is_admin=current_user.is_admin,
    )


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Generate a password reset token. Always returns 200 to prevent user enumeration."""
    user = db.query(User).filter(User.username == body.username).first()
    if user and user.hashed_password:
        raw_token, token_hash = create_refresh_token()
        expires_at = datetime.utcnow() + timedelta(minutes=settings.PASSWORD_RESET_EXPIRY_MINUTES)

        # Invalidate any existing unused tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False,  # noqa: E712
        ).update({"used": True})

        db_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(db_token)
        db.commit()

        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
        logger.info(
            "Password reset requested | user=%s reset_url=%s",
            user.username, reset_url,
        )
        # TODO: send reset_url via email service when configured

    return {"message": "If the account exists, a reset link has been sent"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Reset password using a valid token from /forgot-password."""
    if len(body.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 6 characters",
        )

    token_hash = hash_token(body.token)
    db_token = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used == False,  # noqa: E712
            PasswordResetToken.expires_at > datetime.utcnow(),
        )
        .first()
    )

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")

    user.hashed_password = get_password_hash(body.new_password)
    db_token.used = True

    # Revoke all refresh tokens for this user (force re-login everywhere)
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked == False,  # noqa: E712
    ).update({"revoked": True})

    db.commit()
    return {"message": "Password updated. Please sign in again."}


@router.post("/link-telegram", response_model=UserInfo)
async def link_telegram(
    request: LinkTelegramRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserInfo:
    """Link a Telegram account to the authenticated user."""
    existing = db.query(User).filter(
        User.telegram_id == request.telegram_id,
        User.id != current_user.id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Telegram account is already linked to another user",
        )

    current_user.telegram_id = request.telegram_id
    db.commit()
    db.refresh(current_user)

    return UserInfo(
        id=str(current_user.id),
        username=current_user.username or "",
        name=current_user.name,
        telegram_id=current_user.telegram_id,
        is_admin=current_user.is_admin,
    )
