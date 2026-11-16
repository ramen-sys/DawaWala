from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    # bcrypt only uses the first 72 bytes; longer inputs are rejected by schema validation.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# Used to keep login timing similar whether or not the e-mail exists (FR-2).
DUMMY_PASSWORD_HASH = hash_password("dummy-password-1")


def create_access_token(user_id: int, role: str) -> tuple[str, int]:
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "type": "access",
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires_in


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None
