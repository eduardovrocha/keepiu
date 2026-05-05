"""Instagram URL utilities — detection only, no OAuth or Graph API."""
import re
from typing import Optional

_IG_POST_RE = re.compile(
    r"instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_\-]+)"
)


def is_instagram_url(url: str) -> bool:
    if not url:
        return False
    return bool(_IG_POST_RE.search(url))


def extract_shortcode(url: str) -> Optional[str]:
    m = _IG_POST_RE.search(url)
    return m.group(1) if m else None
