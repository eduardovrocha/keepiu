from urllib.parse import urlparse

SOURCE_RULES: dict[str, list[str]] = {
    "instagram": ["instagram.com"],
    "youtube": ["youtube.com", "youtu.be"],
    "linkedin": ["linkedin.com"],
}


def detect_source(url: str) -> str:
    """Return the source platform name for a URL, or 'unknown' if unrecognised."""
    if not url:
        return "unknown"
    try:
        domain = urlparse(url).netloc.lower()
    except Exception:
        return "unknown"
    for source, domains in SOURCE_RULES.items():
        if any(d in domain for d in domains):
            return source
    return "unknown"
