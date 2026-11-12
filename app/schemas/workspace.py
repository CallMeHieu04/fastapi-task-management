from datetime import datetime

from pydantic import ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.constants import (
    MSG_CANNOT_BE_BLANK,
    MSG_CANNOT_BE_NULL,
    WORKSPACE_NAME_MAX_LENGTH,
    WORKSPACE_NAME_MIN_LENGTH,
)
from app.models.enums import WorkspaceMemberRole
from app.schemas.common import BaseAppModel


class WorkspaceBase(BaseAppModel):
    """Base workspace schema."""

    name: str = Field(
        ...,
        min_length=WORKSPACE_NAME_MIN_LENGTH,
        max_length=WORKSPACE_NAME_MAX_LENGTH,
        description="Workspace display name",
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Name"))
        return v.strip()


class WorkspaceCreate(WorkspaceBase):
    """Schema for creating a workspace."""

    pass


class WorkspaceUpdate(BaseAppModel):
    """Schema for updating workspace attributes."""

    name: str | None = Field(
        default=None,
        min_length=WORKSPACE_NAME_MIN_LENGTH,
        max_length=WORKSPACE_NAME_MAX_LENGTH,
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError(MSG_CANNOT_BE_NULL.format(field="Name"))
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Name"))
        return v.strip()


class WorkspaceMemberAdd(BaseAppModel):
    """Schema for inviting/adding a user to a workspace."""

    user_id: int | None = Field(default=None, description="Target user identifier")
    email: EmailStr | None = Field(default=None, description="Target user email address")
    role: WorkspaceMemberRole = Field(
        default=WorkspaceMemberRole.VIEWER,
        description="Role within workspace (EDITOR or VIEWER)",
    )

    @model_validator(mode="after")
    def validate_identifier_provided(self) -> "WorkspaceMemberAdd":
        if self.user_id is None and self.email is None:
            raise ValueError("Either user_id or email must be provided.")
        return self


class WorkspaceMemberResponse(BaseAppModel):
    """Member profile within a workspace."""

    user_id: int
    email: str | None = None
    full_name: str | None = None
    role: WorkspaceMemberRole

    model_config = ConfigDict(from_attributes=True)


class WorkspaceResponse(BaseAppModel):
    """Complete workspace representation."""

    id: int
    name: str
    owner_id: int
    created_at: datetime
    members: list[WorkspaceMemberResponse] = []

    model_config = ConfigDict(from_attributes=True)
