from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CarouselItem:
    """A single slide from an Instagram carousel post."""
    index: int
    url: str
    media_type: str  # "IMAGE" | "VIDEO"
    image_bytes: Optional[bytes] = None


@dataclass
class CaptureResult:
    success: bool
    url: str
    caption: Optional[str] = None
    image_url: Optional[str] = None       # first image URL (backward compat)
    image_bytes: Optional[bytes] = None   # first image bytes (backward compat)
    username: Optional[str] = None
    shortcode: Optional[str] = None
    is_carousel: bool = False
    carousel_items: list = field(default_factory=list)  # list[CarouselItem]
    # "LOGIN_REQUIRED" | "NOT_FOUND" | "TIMEOUT" | "PARSE_ERROR"
    error_type: Optional[str] = None
    error_message: Optional[str] = None
