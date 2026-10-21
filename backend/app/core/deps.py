from typing import Annotated

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False, description="Paste the access_token returned by /auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def _unauthorized(message: str) -> AppError:
    return AppError(
        status.HTTP_401_UNAUTHORIZED,
        "not_authenticated",
        message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Please log in to continue.")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise _unauthorized("Your session is invalid or has expired. Please log in again.")
    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("Your session is invalid or has expired. Please log in again.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
