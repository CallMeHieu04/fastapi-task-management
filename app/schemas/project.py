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
    """Base project schema."""

    name: str = Field(
        ...,
        min_length=PROJECT_NAME_MIN_LENGTH,
        max_length=PROJECT_NAME_MAX_LENGTH,
        description="Project name",
    )
    description: str | None = Field(
        default=None,
        max_length=PROJECT_DESC_MAX_LENGTH,
        description="Project description",
    )
    status: ProjectStatus = Field(
        default=ProjectStatus.ACTIVE,
        description="Project status",
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Name"))
        return v.strip()


class ProjectCreate(ProjectBase):
    """Schema for creating a new project."""

    pass


class ProjectUpdate(BaseAppModel):
    """Schema for partial update of a project (PATCH)."""

    name: str | None = Field(
        default=None,
        min_length=PROJECT_NAME_MIN_LENGTH,
        max_length=PROJECT_NAME_MAX_LENGTH,
    )
    description: str | None = Field(
        default=None,
        max_length=PROJECT_DESC_MAX_LENGTH,
    )
    status: ProjectStatus | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError(MSG_CANNOT_BE_NULL.format(field="Name"))
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Name"))
        return v.strip()

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: ProjectStatus | None) -> ProjectStatus | None:
        if v is None:
            raise ValueError(MSG_CANNOT_BE_NULL.format(field="Status"))
        return v


class ProjectResponse(ProjectBase):
    """Schema returned for project queries."""

    id: int
    workspace_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
