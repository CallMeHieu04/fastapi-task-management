from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CommentBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

    model_config = ConfigDict(str_strip_whitespace=True)


class CommentCreate(CommentBase):
    pass


class CommentResponse(CommentBase):
    id: int
    task_id: int
    author_id: int
    author_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
