from datetime import datetime

from pydantic import ConfigDict, EmailStr, Field, field_validator

from app.core.constants import (
    MSG_CANNOT_BE_BLANK,
    MSG_CANNOT_BE_NULL,
    WORKSPACE_NAME_MAX_LENGTH,
    WORKSPACE_NAME_MIN_LENGTH,
)
from app.models.enums import WorkspaceMemberRole
from app.schemas.common import BaseAppModel


class WorkspaceMemberResponse(BaseAppModel):
    user_id: int
    email: str | None = None
    full_name: str | None = None
    role: WorkspaceMemberRole

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMemberAdd(BaseAppModel):
    user_id: int | None = Field(None, description="User ID to invite")
    email: EmailStr | None = Field(None, description="Or user email to invite")
    role: WorkspaceMemberRole = Field(default=WorkspaceMemberRole.VIEWER)


class WorkspaceBase(BaseAppModel):
    name: str = Field(
        ...,
        min_length=WORKSPACE_NAME_MIN_LENGTH,
        max_length=WORKSPACE_NAME_MAX_LENGTH,
        description="Name of the workspace",
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Workspace name"))
        return v.strip()


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceUpdate(BaseAppModel):
    name: str | None = Field(
        default=None,
        min_length=WORKSPACE_NAME_MIN_LENGTH,
        max_length=WORKSPACE_NAME_MAX_LENGTH,
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError(MSG_CANNOT_BE_NULL.format(field="Workspace name"))
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Workspace name"))
        return v.strip()


class WorkspaceResponse(WorkspaceBase):
    id: int
    owner_id: int
    created_at: datetime
    members: list[WorkspaceMemberResponse] = []

    model_config = ConfigDict(from_attributes=True)
