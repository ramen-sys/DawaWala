from datetime import datetime, timedelta, timezone

from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import DUMMY_PASSWORD_HASH, hash_password, verify_password
from app.models import User
from app.models.enums import AuthEventType
from app.schemas.auth import UserRegister
from app.services.auth_event_service import record_event

GENERIC_LOGIN_ERROR = "Incorrect e-mail or password."


def register_user(db: Session, data: UserRegister, ip: str | None) -> User:
    if db.scalar(select(User.id).where(User.email == data.email)) is not None:
        raise _email_taken()
    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _email_taken() from None
    db.refresh(user)
    record_event(db, AuthEventType.REGISTER, user.id, ip)
    return user


def _email_taken() -> AppError:
    return AppError(
        status.HTTP_409_CONFLICT,
        "email_taken",
        "An account with this e-mail already exists. Try logging in instead.",
        fields={"email": "This e-mail is already registered."},
    )


def _locked_error(locked_until: datetime) -> AppError:
    minutes = max(1, int((locked_until - datetime.now(timezone.utc)).total_seconds() // 60) + 1)
    return AppError(
        status.HTTP_423_LOCKED,
        "account_locked",
        f"Too many failed login attempts. Please try again in {minutes} minute(s).",
    )


def authenticate_user(db: Session, email: str, password: str, ip: str | None) -> User:
    """FR-2 / SEC-03: lock the account for LOCKOUT_MIN after MAX_FAILED_LOGINS consecutive failures."""
    now = datetime.now(timezone.utc)
    user = db.scalar(select(User).where(User.email == email).with_for_update())

    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        db.rollback()
        record_event(db, AuthEventType.LOGIN_FAILED, None, ip)
        raise AppError(status.HTTP_401_UNAUTHORIZED, "invalid_credentials", GENERIC_LOGIN_ERROR)

    if user.locked_until and user.locked_until > now:
        db.rollback()
        record_event(db, AuthEventType.LOGIN_REFUSED_LOCKED, user.id, ip)
        raise _locked_error(user.locked_until)

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        record_event(db, AuthEventType.LOGIN_FAILED, user.id, ip, commit=False)
        if user.failed_login_attempts >= settings.MAX_FAILED_LOGINS:
            user.failed_login_attempts = 0
            user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MIN)
            record_event(db, AuthEventType.ACCOUNT_LOCKED, user.id, ip, commit=False)
            db.commit()
            raise _locked_error(user.locked_until)
        db.commit()
        raise AppError(status.HTTP_401_UNAUTHORIZED, "invalid_credentials", GENERIC_LOGIN_ERROR)

    user.failed_login_attempts = 0
    user.locked_until = None
    record_event(db, AuthEventType.LOGIN_SUCCESS, user.id, ip, commit=False)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User, ip: str | None) -> None:
    """SEC-08: removes the account and, via ON DELETE CASCADE, all lists, items, images, factors and results.

    The deletion event is recorded without a user ID, because the account no longer exists.
    """
    db.delete(user)
    record_event(db, AuthEventType.ACCOUNT_DELETED, None, ip, commit=False)
    db.commit()
