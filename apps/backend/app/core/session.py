"""HMAC-signed session tokens for single_user mode.

Token format: base64url(json_payload).hmac_hex
"""
import base64
import hashlib
import hmac
import json
import time
from typing import Optional

SESSION_COOKIE = "session"
SESSION_MAX_AGE = 30 * 86400  # 30 days


def sign_session(user_id: str, secret: str) -> str:
    payload = {"uid": user_id, "iat": int(time.time())}
    data = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    sig = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}.{sig}"


def verify_session(token: str, secret: str) -> Optional[str]:
    """Return user_id if token is valid, else None."""
    if not secret or not token:
        return None
    try:
        data, sig = token.rsplit(".", 1)
        expected = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(data + "==").decode())
        return str(payload["uid"])
    except Exception:
        return None
