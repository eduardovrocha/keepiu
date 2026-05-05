import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Boolean, Text, BigInteger, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
from app.core.database import Base


class Content(Base):
    __tablename__ = "contents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    source = Column(String(50), default="telegram", nullable=False)
    type = Column(String(50), nullable=False)  # text, link, image, forward

    # Raw data
    raw_text = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)  # OCR result

    # Link specific
    url = Column(Text, nullable=True)

    # Processed data
    title = Column(String(500), nullable=True)
    summary = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    tags = Column(JSONB, default=list)
    importance_score = Column(Integer, default=0)
    actionable = Column(Boolean, default=False)

    # Status: queued | processing | completed | failed
    status = Column(String(50), default="queued", nullable=False, index=True)
    # Stage: queued | capturing | ocr | ai_processing | finalizing | completed | failed
    processing_stage = Column(String(50), default="queued", nullable=True)
    processed = Column(Boolean, default=False, nullable=False, index=True)
    processing_error = Column(Text, nullable=True)
    processing_started_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, nullable=True)

    # Ingestion channel metadata
    ingestion_channel = Column(String(20), nullable=True, index=True)  # telegram | whatsapp
    external_message_id = Column(String(120), nullable=True)
    external_user_id = Column(String(120), nullable=True, index=True)
    sender_name = Column(String(255), nullable=True)

    # Telegram-specific metadata (kept for backward compat)
    telegram_message_id = Column(BigInteger, nullable=True)
    telegram_chat_id = Column(BigInteger, nullable=True)

    # Transcript (audio/video STT)
    transcript = Column(Text, nullable=True)
    transcript_language = Column(String(20), nullable=True)
    transcript_confidence = Column(Float, nullable=True)

    # Instagram Agent
    instagram_agent_processed = Column(Boolean, default=False, nullable=False, index=True)

    # Carousel OCR blocks: [{"index": 0, "text": "...", "confidence": 0.9}, ...]
    ocr_blocks = Column(JSONB, nullable=True)

    # Instagram Intelligence fields
    source_platform = Column(String(50), nullable=True, index=True)  # 'instagram'
    external_id = Column(String(200), nullable=True)  # shortcode
    caption = Column(Text, nullable=True)
    tone = Column(String(100), nullable=True)
    niche = Column(String(100), nullable=True)
    cta = Column(String(500), nullable=True)
    confidence_score_ocr = Column(Float, nullable=True)
    language_detected = Column(String(20), nullable=True)
    sentiment_score = Column(Float, nullable=True)

    # Reprocessing
    last_reprocess_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="contents")
    embedding = relationship("ContentEmbedding", uselist=False, back_populates="content")
    
    def __repr__(self):
        return f"<Content(id={self.id}, type={self.type}, user_id={self.user_id})>"


class ContentEmbedding(Base):
    __tablename__ = "content_embeddings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_id = Column(UUID(as_uuid=True), ForeignKey("contents.id"), nullable=False, unique=True)
    vector = Column(Vector(1536), nullable=False)  # OpenAI embedding dimension
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    content = relationship("Content", back_populates="embedding")
    
    def __repr__(self):
        return f"<ContentEmbedding(id={self.id}, content_id={self.content_id})>"
