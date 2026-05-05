from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.settings_service import SettingsService, SETTING_DEFINITIONS
from app.schemas.settings import (
    SettingResponse,
    SettingRevealResponse,
    SettingsRevealAllResponse,
    SettingsBatchUpdate,
    TestSettingsResponse,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def _require_admin(current_user: User) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


@router.get("", response_model=List[SettingResponse])
def list_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all system settings. Secret values are masked."""
    _require_admin(current_user)
    return SettingsService(db).get_all()


@router.put("", response_model=List[SettingResponse])
def update_settings(
    payload: SettingsBatchUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Batch-update one or more system settings."""
    _require_admin(current_user)
    svc = SettingsService(db)
    svc.batch_update(payload.settings)
    return svc.get_all()


# ── Static sub-routes — must be declared before /{key} patterns ──────────────

@router.post("/reveal", response_model=SettingsRevealAllResponse)
def reveal_all_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return plain (unmasked) values for all settings in a single call.
    Used by the admin UI to pre-populate form fields on page load."""
    _require_admin(current_user)
    values = SettingsService(db).reveal_all()
    return SettingsRevealAllResponse(values=values)


@router.post("/test", response_model=TestSettingsResponse)
def test_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Validate all credentials by calling external APIs.
    Uses DB values (with env fallback). Never returns secrets in response."""
    _require_admin(current_user)
    return SettingsService(db).test_connectivity()


# ── Dynamic key routes ────────────────────────────────────────────────────────

@router.get("/{key}", response_model=SettingResponse)
def get_setting(
    key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a single setting. Secret value is masked."""
    _require_admin(current_user)
    if key not in SETTING_DEFINITIONS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown key")
    all_settings = {s.key: s for s in SettingsService(db).get_all()}
    if key not in all_settings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
    return all_settings[key]


@router.post("/{key}/reveal", response_model=SettingRevealResponse)
def reveal_setting(
    key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the plain (unmasked) value of a single setting."""
    _require_admin(current_user)
    if key not in SETTING_DEFINITIONS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown key")
    value = SettingsService(db).reveal(key)
    return SettingRevealResponse(key=key, value=value)
