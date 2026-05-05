from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, field_validator


class SettingResponse(BaseModel):
    key: str
    display_value: Optional[str]  # masked when is_secret=True
    is_secret: bool
    has_value: bool
    updated_at: datetime

    class Config:
        from_attributes = True


class SettingRevealResponse(BaseModel):
    key: str
    value: Optional[str]


class SettingsRevealAllResponse(BaseModel):
    # key → plain value (None if not set)
    values: Dict[str, Optional[str]]


class SettingUpdate(BaseModel):
    key: str
    value: str

    @field_validator("value")
    @classmethod
    def value_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Value cannot be empty")
        return v.strip()


class SettingsBatchUpdate(BaseModel):
    settings: List[SettingUpdate]


class CheckResult(BaseModel):
    ok: bool
    message: str


class TestSettingsResponse(BaseModel):
    overall: bool
    checks: Dict[str, CheckResult]
