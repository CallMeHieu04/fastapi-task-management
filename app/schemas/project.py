from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from app.core.constants import (
    MSG_CANNOT_BE_BLANK,
    MSG_CANNOT_BE_NULL,
    PROJECT_DESC_MAX_LENGTH,
    PROJECT_NAME_MAX_LENGTH,
    PROJECT_NAME_MIN_LENGTH,
)
from app.models.enums import ProjectStatus
from app.schemas.common import BaseAppModel


class ProjectBase(BaseAppModel):
    name: str = Field(
        ...,
        min_length=PROJECT_NAME_MIN_LENGTH,
        max_length=PROJECT_NAME_MAX_LENGTH,
    )
    description: str | None = Field(default=None, max_length=PROJECT_DESC_MAX_LENGTH)

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Project name"))
        return v.strip()


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseAppModel):
    name: str | None = Field(
        default=None,
        min_length=PROJECT_NAME_MIN_LENGTH,
        max_length=PROJECT_NAME_MAX_LENGTH,
    )
    description: str | None = Field(default=None, max_length=PROJECT_DESC_MAX_LENGTH)
    status: ProjectStatus | None = Field(default=None)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError(MSG_CANNOT_BE_NULL.format(field="Project name"))
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Project name"))
        return v.strip()

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: ProjectStatus | None) -> ProjectStatus | None:
        if v is None:
            raise ValueError(MSG_CANNOT_BE_NULL.format(field="Status"))
        return v


class ProjectResponse(ProjectBase):
    id: int
    workspace_id: int
    status: ProjectStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
