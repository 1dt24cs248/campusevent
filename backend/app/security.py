"""Authentication utilities: password hashing and JWT token management."""
import bcrypt
from datetime import timedelta
from jose import jwt
from app.config import settings
from app.clock import get_now


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    now = get_now()
    expire = now + (expires_delta if expires_delta else timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
