import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
import bcrypt
from jose import JWTError, jwt
from app.core.config import get_settings

settings = get_settings()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    try:
        password_bytes = plain_password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    password_bytes = password.encode('utf-8')
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_EXPIRATION_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def create_refresh_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hash). Store the hash; send raw_token to the client."""
    raw = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, token_hash


def hash_token(raw_token: str) -> str:
    """SHA-256 hash a raw token for DB lookup."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def encrypt_setting(value: str, fernet_key: str) -> str:
    """Encrypt a setting value with Fernet (AES-128-CBC + HMAC)."""
    from cryptography.fernet import Fernet
    return Fernet(fernet_key.encode()).encrypt(value.encode()).decode()


def decrypt_setting(ciphertext: str, fernet_key: str) -> str:
    """Decrypt a Fernet-encrypted setting. Returns raw value if decryption fails (legacy plaintext)."""
    from cryptography.fernet import Fernet, InvalidToken
    try:
        return Fernet(fernet_key.encode()).decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception):
        return ciphertext
