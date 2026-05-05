import logging
from typing import Dict, Optional

import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _parse_metadata(html: str, url: str) -> Dict[str, Optional[str]]:
    """Extract title, description, og_image and domain from raw HTML."""
    parsed = urlparse(url)
    result: Dict[str, Optional[str]] = {
        "title": None,
        "description": None,
        "og_image": None,
        "domain": parsed.netloc,
    }

    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("title")
    if title_tag:
        result["title"] = title_tag.get_text(strip=True)

    og_title = soup.find("meta", property="og:title")
    if og_title and not result["title"]:
        result["title"] = og_title.get("content", "").strip() or None

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc:
        result["description"] = meta_desc.get("content", "").strip() or None

    og_desc = soup.find("meta", property="og:description")
    if og_desc and not result["description"]:
        result["description"] = og_desc.get("content", "").strip() or None

    og_image = soup.find("meta", property="og:image")
    if og_image:
        result["og_image"] = og_image.get("content", "").strip() or None

    return result


def extract_link_metadata_sync(url: str) -> Dict[str, Optional[str]]:
    """
    Synchronous metadata extractor — safe to call from Celery workers.
    Uses httpx.Client (blocking) to avoid event-loop conflicts.
    """
    empty: Dict[str, Optional[str]] = {
        "title": None,
        "description": None,
        "og_image": None,
        "domain": None,
    }

    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return empty

        with httpx.Client(
            follow_redirects=True,
            timeout=10.0,
            headers=_HEADERS,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return _parse_metadata(response.text, url)

    except Exception as exc:
        logger.warning("Failed to extract metadata from %s: %s", url, exc)
        return empty


async def extract_link_metadata(url: str) -> Dict[str, Optional[str]]:
    """
    Async metadata extractor — for use in FastAPI request handlers.
    Uses httpx.AsyncClient.
    """
    empty: Dict[str, Optional[str]] = {
        "title": None,
        "description": None,
        "og_image": None,
        "domain": None,
    }

    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return empty

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10.0,
            headers=_HEADERS,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return _parse_metadata(response.text, url)

    except Exception as exc:
        logger.warning("Failed to extract metadata from %s: %s", url, exc)
        return empty
