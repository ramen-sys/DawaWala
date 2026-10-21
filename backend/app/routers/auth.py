from fastapi import APIRouter, Request, status

from app.core.deps import CurrentUser, DbSession, client_ip
from app.core.security import create_access_token
from app.schemas.auth import RegisterResponse, TokenResponse, UserLogin, UserOut, UserRegister
from app.schemas.common import ErrorResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="FR-1: Register a new user",
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def register(data: UserRegister, db: DbSession, request: Request):
    user = auth_service.register_user(db, data, client_ip(request))
    return RegisterResponse(message="Account created. You can now log in.", user=UserOut.model_validate(user))


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="FR-2: Log in and receive a JWT (30-minute lifetime)",
    responses={401: {"model": ErrorResponse}, 423: {"model": ErrorResponse}},
)
def login(data: UserLogin, db: DbSession, request: Request):
    user = auth_service.authenticate_user(db, data.email, data.password, client_ip(request))
    token, expires_in = create_access_token(user.id, user.role.value)
    return TokenResponse(access_token=token, expires_in=expires_in, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut, summary="Current user profile", responses={401: {"model": ErrorResponse}})
def me(user: CurrentUser):
    return user


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="SEC-08: Delete my account and all my data",
    responses={401: {"model": ErrorResponse}},
)
def delete_me(user: CurrentUser, db: DbSession, request: Request):
    auth_service.delete_user(db, user, client_ip(request))
