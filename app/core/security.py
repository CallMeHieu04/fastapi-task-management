import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import settings
from app.core.constants import (
    MSG_ACCESS_TOKEN_REQUIRED,
    MSG_COULD_NOT_VALIDATE,
    MSG_REFRESH_TOKEN_REQUIRED,
    PASSWORD_MAX_BYTES,
)
from app.core.exceptions import UnauthorizedException
from app.models.enums import TokenType

# Pre-computed valid bcrypt hash used to prevent user-enumeration timing attacks during login
DUMMY_PASSWORD_HASH = "$2b$12$e86gXh8YtZlOq05nFomxXe9jS1x1ZlOq05nFomxXe9jS1x1ZlOq05"


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt, enforcing 72-byte limit."""
    pwd_bytes = password.encode("utf-8")
    if len(pwd_bytes) > PASSWORD_MAX_BYTES:
        raise ValueError(f"Password cannot exceed {PASSWORD_MAX_BYTES} bytes.")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    pwd_bytes = plain_password.encode("utf-8")
    if len(pwd_bytes) > PASSWORD_MAX_BYTES:
        return False
    hash_bytes = hashed_password.encode("utf-8")
    try:
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except (ValueError, TypeError):
        return False


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """Run CPU-bound bcrypt verification off the main event loop in a worker thread."""
    return await asyncio.to_thread(verify_password, plain_password, hashed_password)


def create_access_token(
    subject: Any,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token with type, iat, exp, and jti."""
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "type": TokenType.ACCESS.value,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    subject: Any,
    expires_delta: timedelta | None = None,
) -> tuple[str, str, datetime]:
    """Create a signed JWT refresh token. Returns (token_str, jti, expire_datetime)."""
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    token_jti = str(uuid.uuid4())
    to_encode = {
        "sub": str(subject),
        "type": TokenType.REFRESH.value,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": token_jti,
    }

    token_str = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token_str, token_jti, expire


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token. Raises PyJWTError on failure."""
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        options={"require": ["exp", "sub", "jti", "type"]},
    )


def decode_token_claim(token: str, expected_type: str) -> tuple[int, str]:
    """Validate token claims and structure, returning (user_id, jti) or raising UnauthorizedException."""
    try:
        payload = decode_token(token)
    except jwt.PyJWTError as err:
        raise UnauthorizedException(MSG_COULD_NOT_VALIDATE) from err

    token_type = payload.get("type")
    if token_type != expected_type:
        if expected_type == TokenType.ACCESS.value:
            raise UnauthorizedException(MSG_ACCESS_TOKEN_REQUIRED)
        raise UnauthorizedException(MSG_REFRESH_TOKEN_REQUIRED)

    sub_raw = payload.get("sub")
    jti = payload.get("jti")
    if sub_raw is None or jti is None:
        raise UnauthorizedException(MSG_COULD_NOT_VALIDATE)

    try:
        user_id = int(sub_raw)
    except (ValueError, TypeError) as err:
        raise UnauthorizedException(MSG_COULD_NOT_VALIDATE) from err

    return user_id, str(jti)
