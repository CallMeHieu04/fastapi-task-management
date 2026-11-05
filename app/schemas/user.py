from datetime import datetime

from pydantic import ConfigDict, EmailStr, Field, field_validator

from app.core.constants import (
    MSG_CANNOT_BE_BLANK,
    MSG_CANNOT_BE_NULL,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    USER_NAME_MAX_LENGTH,
    USER_NAME_MIN_LENGTH,
)
from app.models.enums import UserRole
from app.schemas.common import BaseAppModel


class UserBase(BaseAppModel):
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
    password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description="Plaintext password",
    )
    role: UserRole | None = Field(default=UserRole.MEMBER, description="System role")


class UserLogin(BaseAppModel):
    email: EmailStr
    password: str


class UserUpdate(BaseAppModel):
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
    current_password: str = Field(..., min_length=PASSWORD_MIN_LENGTH)
    new_password: str = Field(..., min_length=PASSWORD_MIN_LENGTH)


class UserResponse(UserBase):
    id: int
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
