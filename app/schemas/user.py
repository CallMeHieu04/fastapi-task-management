from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User's unique email address")
    full_name: str = Field(..., min_length=2, max_length=100, description="Full display name")

    model_config = ConfigDict(str_strip_whitespace=True)


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100, description="Plaintext password")
    role: UserRole | None = Field(default=UserRole.MEMBER, description="System role")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=100)
    email: EmailStr | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class ChangePassword(BaseModel):
    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=6)


class UserResponse(UserBase):
    id: int
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
