from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator
from uuid import UUID


class UserBase(BaseModel):
    telegram_id: Optional[int] = None
    name: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserRegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    telegram_id: Optional[int] = None

    @field_validator("username")
    @classmethod
    def username_min_length(cls, v: str) -> str:
        if len(v.strip()) < 3:
            raise ValueError("Username must be at least 3 characters")
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class UserRegisterResponse(BaseModel):
    id: UUID
    username: str
    email: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserResponse(UserBase):
    id: UUID
    username: Optional[str] = None
    email: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class LinkTelegramRequest(BaseModel):
    telegram_id: int
