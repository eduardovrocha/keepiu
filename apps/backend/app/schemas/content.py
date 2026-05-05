from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from uuid import UUID


class ContentBase(BaseModel):
    type: str  # text, link, image, forward
    raw_text: Optional[str] = None


class ContentCreate(ContentBase):
    user_id: Optional[UUID] = None
    source: str = "telegram"
    ingestion_channel: Optional[str] = "telegram"
    external_message_id: Optional[str] = None
    external_user_id: Optional[str] = None
    sender_name: Optional[str] = None
    telegram_id: Optional[int] = None
    telegram_message_id: Optional[int] = None
    telegram_chat_id: Optional[int] = None
    url: Optional[str] = None
    source_platform: Optional[str] = None


class ContentSubmit(BaseModel):
    source_url: str
    source_platform: str = "instagram"


class ContentUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    importance_score: Optional[int] = None
    actionable: Optional[bool] = None


class ContentResponse(ContentBase):
    id: UUID
    user_id: UUID
    source: str
    status: str = "queued"
    processing_stage: Optional[str] = None
    extracted_text: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = []
    importance_score: int = 0
    actionable: bool = False
    processed: bool = False
    processing_error: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Ingestion metadata
    ingestion_channel: Optional[str] = None
    sender_name: Optional[str] = None

    # Instagram Intelligence fields
    source_platform: Optional[str] = None
    external_id: Optional[str] = None
    caption: Optional[str] = None
    tone: Optional[str] = None
    niche: Optional[str] = None
    cta: Optional[str] = None
    confidence_score_ocr: Optional[float] = None
    language_detected: Optional[str] = None
    sentiment_score: Optional[float] = None

    # Audio/video transcript
    transcript: Optional[str] = None
    transcript_language: Optional[str] = None
    transcript_confidence: Optional[float] = None

    # Carousel OCR blocks: [{"index": 0, "text": "...", "confidence": 0.9}, ...]
    ocr_blocks: Optional[list] = None

    class Config:
        from_attributes = True


class ContentListResponse(BaseModel):
    items: List[ContentResponse]
    total: int
    page: int
    page_size: int


class ContentProcessingResponse(BaseModel):
    id: UUID
    url: Optional[str] = None
    source_platform: Optional[str] = None
    ingestion_channel: Optional[str] = None
    status: str
    processing_stage: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
