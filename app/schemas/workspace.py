from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import WorkspaceMemberRole


class WorkspaceMemberResponse(BaseModel):
    user_id: int
    email: str | None = None
    full_name: str | None = None
    role: WorkspaceMemberRole

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMemberAdd(BaseModel):
    user_id: int | None = Field(None, description="User ID to invite")
    email: EmailStr | None = Field(None, description="Or user email to invite")
    role: WorkspaceMemberRole = Field(default=WorkspaceMemberRole.VIEWER)


class WorkspaceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Name of the workspace")

    model_config = ConfigDict(str_strip_whitespace=True)


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)

    model_config = ConfigDict(str_strip_whitespace=True)


class WorkspaceResponse(WorkspaceBase):
    id: int
    owner_id: int
    created_at: datetime
    members: list[WorkspaceMemberResponse] = []

    model_config = ConfigDict(from_attributes=True)
