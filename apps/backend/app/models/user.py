import uuid
from datetime import datetime
from sqlalchemy import Boolean, Column, String, DateTime, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BigInteger, unique=True, nullable=True, index=True)
    whatsapp_phone = Column(String(30), unique=True, nullable=True, index=True)
    name = Column(String(255), nullable=True)

    # Auth fields (populated via /auth/register)
    username = Column(String(100), unique=True, nullable=True, index=True)
    email = Column(String(255), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False, server_default="false")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    contents = relationship("Content", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    quota = relationship("UserQuota", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, telegram_id={self.telegram_id})>"
