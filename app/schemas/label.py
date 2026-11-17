import re

from pydantic import ConfigDict, Field, field_validator

from app.core.constants import (
    HEX_COLOR_REGEX,
    LABEL_NAME_MAX_LENGTH,
    LABEL_NAME_MIN_LENGTH,
    MSG_CANNOT_BE_BLANK,
    MSG_CANNOT_BE_NULL,
)
from app.schemas.common import BaseAppModel

COLOR_PATTERN = re.compile(HEX_COLOR_REGEX)


class LabelBase(BaseAppModel):
    name: str = Field(
        ...,
        min_length=LABEL_NAME_MIN_LENGTH,
        max_length=LABEL_NAME_MAX_LENGTH,
        description="Label name",
    )
    color: str = Field(
        default="#3B82F6",
        description="Hex color code (e.g. #3B82F6 or #FFF)",
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Name"))
        return v.strip()

    @field_validator("color")
    @classmethod
    def validate_color_format(cls, v: str) -> str:
        if not COLOR_PATTERN.match(v):
            raise ValueError("Color must be a valid hex color code (e.g., #3B82F6 or #FFF).")
        return v


class LabelCreate(LabelBase):
    pass


class LabelUpdate(BaseAppModel):
    name: str | None = Field(
        default=None,
        min_length=LABEL_NAME_MIN_LENGTH,
        max_length=LABEL_NAME_MAX_LENGTH,
    )
    color: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError(MSG_CANNOT_BE_NULL.format(field="Name"))
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Name"))
        return v.strip()

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError(MSG_CANNOT_BE_NULL.format(field="Color"))
        if not COLOR_PATTERN.match(v):
            raise ValueError("Color must be a valid hex color code (e.g., #3B82F6 or #FFF).")
        return v


class LabelResponse(LabelBase):
    id: int
    project_id: int

    model_config = ConfigDict(from_attributes=True)
