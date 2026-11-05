from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from app.core.constants import (
    COMMENT_CONTENT_MAX_LENGTH,
    COMMENT_CONTENT_MIN_LENGTH,
    MSG_CANNOT_BE_BLANK,
)
from app.schemas.common import BaseAppModel


class CommentBase(BaseAppModel):
    content: str = Field(
        ...,
        min_length=COMMENT_CONTENT_MIN_LENGTH,
        max_length=COMMENT_CONTENT_MAX_LENGTH,
    )

    @field_validator("content")
    @classmethod
    def validate_content_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Comment content"))
        return v.strip()


class CommentCreate(CommentBase):
    pass


class CommentResponse(CommentBase):
    id: int
    task_id: int
    author_id: int
    author_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
