import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from jwt import InvalidTokenError

from .config import get_settings

_passwords = PasswordHasher()
_password_work_slots = asyncio.Semaphore(get_settings().password_work_concurrency)


def hash_password(password: str) -> str:
    return _passwords.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _passwords.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


async def hash_password_async(password: str) -> str:
    async with _password_work_slots:
        return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password: str, password_hash: str) -> bool:
    async with _password_work_slots:
        return await asyncio.to_thread(verify_password, password, password_hash)


def create_access_token(user_id: str, role: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "jti": str(uuid4()),
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    claims = jwt.decode(
        token,
        get_settings().jwt_secret,
        algorithms=["HS256"],
        options={"require": ["exp", "sub", "type"]},
    )
    if claims.get("type") != "access" or not isinstance(claims.get("sub"), str):
        raise InvalidTokenError("Invalid access token claims")
    return claims


def new_refresh_token() -> str:
    return token_urlsafe(48)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
