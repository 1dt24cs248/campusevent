"""Encryption helpers for private safety and emergency report content."""
import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import settings


def _cipher() -> Fernet:
    configured_key = settings.APP_ENCRYPTION_KEY.strip()
    secret = configured_key or settings.JWT_SECRET
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_private(value: str | None) -> str | None:
    if value is None:
        return None
    return _cipher().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_private(value: str | None) -> str | None:
    if value is None:
        return None
    return _cipher().decrypt(value.encode("ascii")).decode("utf-8")
