from datetime import UTC, datetime

from pydantic import AwareDatetime, ConfigDict, Field, PositiveInt, field_validator

from app.core.constants import (
    MSG_CANNOT_BE_NULL,
    MSG_DUE_DATE_PAST,
    TASK_DESC_MAX_LENGTH,
    TASK_TITLE_MAX_LENGTH,
    TASK_TITLE_MIN_LENGTH,
)
from app.models.task import TaskPriority, TaskStatus
from app.schemas.common import BaseAppModel


class TaskBase(BaseAppModel):
    title: str = Field(
        ...,
        min_length=TASK_TITLE_MIN_LENGTH,
        max_length=TASK_TITLE_MAX_LENGTH,
        description="Task title",
    )
    description: str | None = Field(default=None, max_length=TASK_DESC_MAX_LENGTH)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    due_date: AwareDatetime | None = None
    assignee_id: PositiveInt | None = None

    @field_validator("due_date")
    @classmethod
    def validate_due_date_future(cls, v: AwareDatetime | None) -> AwareDatetime | None:
        if v is not None and v < datetime.now(UTC):
            raise ValueError(MSG_DUE_DATE_PAST)
        return v


class ProjectTaskCreate(TaskBase):
    """Schema for creating a task within a specific project (URL supplies project_id)."""

    pass


class TaskCreate(TaskBase):
    """Schema for creating a task (project_id optionally supplied in body)."""

    project_id: PositiveInt | None = None


class TaskUpdate(BaseAppModel):
    """Schema for partial update (PATCH). Prevents sending explicit null on required fields."""

    title: str | None = Field(
        default=None,
        min_length=TASK_TITLE_MIN_LENGTH,
        max_length=TASK_TITLE_MAX_LENGTH,
    )
    description: str | None = Field(default=None, max_length=TASK_DESC_MAX_LENGTH)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: AwareDatetime | None = None
    assignee_id: PositiveInt | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError(MSG_CANNOT_BE_NULL.format(field="Title"))
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: TaskStatus | None) -> TaskStatus | None:
        if v is None:
            raise ValueError(MSG_CANNOT_BE_NULL.format(field="Status"))
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: TaskPriority | None) -> TaskPriority | None:
        if v is None:
            raise ValueError(MSG_CANNOT_BE_NULL.format(field="Priority"))
        return v

    @field_validator("due_date")
    @classmethod
    def validate_due_date_future(cls, v: AwareDatetime | None) -> AwareDatetime | None:
        if v is not None and v < datetime.now(UTC):
            raise ValueError(MSG_DUE_DATE_PAST)
        return v


class TaskResponse(TaskBase):
    id: int
    status: TaskStatus
    project_id: int | None = None
    assignee_id: int | None = None
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("due_date", mode="before")
    @classmethod
    def ensure_utc_tz(cls, v: datetime | None) -> datetime | None:
        if v is not None and isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v

    model_config = ConfigDict(from_attributes=True)
