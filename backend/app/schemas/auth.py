import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import settings
from app.models.enums import UserRole


def validate_password_rules(password: str) -> str:
    """SEC-01: at least 8 characters with at least one letter and one digit."""
    if len(password) < settings.PASSWORD_MIN_LEN:
        raise ValueError(f"Password must be at least {settings.PASSWORD_MIN_LEN} characters long.")
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password is too long (maximum 72 bytes).")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("Password must contain at least one letter and one digit.")
    return password


class UserRegister(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Ali Khan"])
    email: EmailStr = Field(examples=["ali@example.com"])
    password: str = Field(examples=["Secret123"])
    role: UserRole = UserRole.PATIENT

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Name is required.")
        return v

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_rules(v)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: UserRole
    created_at: datetime


class RegisterResponse(BaseModel):
    message: str
    user: UserOut


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
