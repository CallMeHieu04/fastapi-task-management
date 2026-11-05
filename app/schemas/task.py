from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from app.core.constants import (
    MSG_CANNOT_BE_BLANK,
    MSG_CANNOT_BE_NULL,
    TASK_DESC_MAX_LENGTH,
    TASK_TITLE_MAX_LENGTH,
    TASK_TITLE_MIN_LENGTH,
)
from app.models.enums import TaskPriority, TaskStatus
from app.schemas.common import BaseAppModel
from app.schemas.label import LabelResponse


class TaskBase(BaseAppModel):
    title: str = Field(
        ...,
        min_length=TASK_TITLE_MIN_LENGTH,
        max_length=TASK_TITLE_MAX_LENGTH,
        description="Task title",
    )
    description: str | None = Field(None, max_length=TASK_DESC_MAX_LENGTH)
    status: TaskStatus = Field(default=TaskStatus.TODO)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    due_date: datetime | None = None

    @field_validator("title")
    @classmethod
    def validate_title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Title"))
        return v.strip()


class TaskCreate(TaskBase):
    assignee_id: int | None = None
    label_ids: list[int] | None = []


class TaskUpdate(BaseAppModel):
    """Schema for updating a task.

    Prevents sending explicit null or whitespace for non-nullable database fields.
    """

    title: str | None = Field(
        default=None,
        min_length=TASK_TITLE_MIN_LENGTH,
        max_length=TASK_TITLE_MAX_LENGTH,
    )
    description: str | None = Field(default=None, max_length=TASK_DESC_MAX_LENGTH)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: datetime | None = None
    assignee_id: int | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError(MSG_CANNOT_BE_NULL.format(field="Title"))
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Title"))
        return v.strip()

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


class TaskResponse(TaskBase):
    id: int
    project_id: int
    assignee_id: int | None = None
    assignee_name: str | None = None
    created_by: int
    created_at: datetime
    labels: list[LabelResponse] = []
    comments_count: int = 0

    model_config = ConfigDict(from_attributes=True)
