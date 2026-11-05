from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProjectStatus


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)

    model_config = ConfigDict(str_strip_whitespace=True)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    status: ProjectStatus | None = Field(default=None)

    model_config = ConfigDict(str_strip_whitespace=True)


class ProjectResponse(ProjectBase):
    id: int
    workspace_id: int
    status: ProjectStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
