from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TaskPriority, TaskStatus
from app.schemas.label import LabelResponse


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)
    status: TaskStatus = Field(default=TaskStatus.TODO)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    due_date: datetime | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class TaskCreate(TaskBase):
    assignee_id: int | None = None
    label_ids: list[int] | None = []


class TaskUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: datetime | None = None
    assignee_id: int | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


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
