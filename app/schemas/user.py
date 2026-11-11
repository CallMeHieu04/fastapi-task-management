from datetime import datetime

from pydantic import ConfigDict, EmailStr, Field, field_validator

from app.core.constants import (
    MSG_CANNOT_BE_BLANK,
    MSG_CANNOT_BE_NULL,
    PASSWORD_MAX_BYTES,
    PASSWORD_MIN_LENGTH,
    USER_NAME_MAX_LENGTH,
    USER_NAME_MIN_LENGTH,
)
from app.models.enums import UserRole
from app.schemas.common import BaseAppModel


def _validate_password_length(password: str) -> str:
    """Helper to validate password length in chars and bytes (bcrypt 72-byte limit)."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(f"Password cannot exceed {PASSWORD_MAX_BYTES} bytes.")
    return password


class UserBase(BaseAppModel):
    """Base schema for user identity."""

    email: EmailStr = Field(..., description="User's unique email address")
    full_name: str = Field(
        ...,
        min_length=USER_NAME_MIN_LENGTH,
        max_length=USER_NAME_MAX_LENGTH,
        description="Full display name",
    )

    @field_validator("full_name")
    @classmethod
    def validate_full_name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Full name"))
        return v.strip()


class UserCreate(UserBase):
    """Schema for public user registration. Note: Client CANNOT choose role."""

    password: str = Field(..., description="Plaintext password")

    @field_validator("password")
    @classmethod
    def validate_password_field(cls, v: str) -> str:
        return _validate_password_length(v)


class UserLogin(BaseAppModel):
    """Schema for logging into account."""

    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password_field(cls, v: str) -> str:
        if len(v.encode("utf-8")) > PASSWORD_MAX_BYTES:
            raise ValueError(f"Password cannot exceed {PASSWORD_MAX_BYTES} bytes.")
        return v


class UserUpdate(BaseAppModel):
    """Schema for updating user profile."""

    full_name: str | None = Field(
        default=None,
        min_length=USER_NAME_MIN_LENGTH,
        max_length=USER_NAME_MAX_LENGTH,
    )
    email: EmailStr | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError(MSG_CANNOT_BE_NULL.format(field="Full name"))
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Full name"))
        return v.strip()


class ChangePassword(BaseAppModel):
    """Schema for user changing their own password."""

    current_password: str = Field(..., description="Existing account password")
    new_password: str = Field(..., description="New replacement password")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password_length(v)


class UserResponse(UserBase):
    """Public user response schema."""

    id: int
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
