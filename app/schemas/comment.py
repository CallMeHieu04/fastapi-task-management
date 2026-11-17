from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from app.core.constants import (
    COMMENT_CONTENT_MAX_LENGTH,
    COMMENT_CONTENT_MIN_LENGTH,
    MSG_CANNOT_BE_BLANK,
    MSG_CANNOT_BE_NULL,
)
from app.schemas.common import BaseAppModel


class CommentAuthor(BaseAppModel):
    id: int
    email: str
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class CommentBase(BaseAppModel):
    content: str = Field(
        ...,
        min_length=COMMENT_CONTENT_MIN_LENGTH,
        max_length=COMMENT_CONTENT_MAX_LENGTH,
        description="Comment text content",
    )

    @field_validator("content")
    @classmethod
    def validate_content_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Content"))
        return v.strip()


class CommentCreate(CommentBase):
    pass


class CommentUpdate(BaseAppModel):
    content: str | None = Field(
        default=None,
        min_length=COMMENT_CONTENT_MIN_LENGTH,
        max_length=COMMENT_CONTENT_MAX_LENGTH,
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError(MSG_CANNOT_BE_NULL.format(field="Content"))
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Content"))
        return v.strip()


class CommentResponse(CommentBase):
    id: int
    task_id: int
    author_id: int
    author: CommentAuthor | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
