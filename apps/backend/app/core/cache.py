import json
import logging
from typing import Any, Optional

import redis
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[redis.Redis] = None


def get_redis() -> Optional[redis.Redis]:
    global _client
    if _client is None:
        try:
            settings = get_settings()
            _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            _client.ping()
        except Exception as exc:
            logger.warning("Redis unavailable — caching disabled: %s", exc)
            _client = None
    return _client


def cache_get(key: str) -> Optional[Any]:
    client = get_redis()
    if client is None:
        return None
    try:
        raw = client.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        logger.warning("cache_get failed for key=%s: %s", key, exc)
        return None


def cache_set(key: str, value: Any, ttl: int) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        client.setex(key, ttl, json.dumps(value))
    except Exception as exc:
        logger.warning("cache_set failed for key=%s: %s", key, exc)


def cache_delete_pattern(pattern: str) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        keys = client.keys(pattern)
        if keys:
            client.delete(*keys)
    except Exception as exc:
        logger.warning("cache_delete_pattern failed: %s", exc)
