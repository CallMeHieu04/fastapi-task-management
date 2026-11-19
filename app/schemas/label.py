import re

from pydantic import ConfigDict, Field, field_validator

from app.core.constants import (
    DEFAULT_LABEL_COLOR,
    HEX_COLOR_REGEX,
    LABEL_NAME_MAX_LENGTH,
    LABEL_NAME_MIN_LENGTH,
    MSG_CANNOT_BE_BLANK,
    MSG_CANNOT_BE_NULL,
    MSG_INVALID_HEX_COLOR,
)
from app.schemas.common import BaseAppModel

COLOR_PATTERN = re.compile(HEX_COLOR_REGEX)


def validate_hex_color(v: str) -> str:
    """Validate hex color string format (#RGB or #RRGGBB)."""
    if not COLOR_PATTERN.match(v):
        raise ValueError(MSG_INVALID_HEX_COLOR)
    return v


def validate_not_blank_name(v: str) -> str:
    """Validate that name string is not empty or only whitespace."""
    if not v.strip():
        raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Name"))
    return v.strip()


class LabelBase(BaseAppModel):
    name: str = Field(
        ...,
        min_length=LABEL_NAME_MIN_LENGTH,
        max_length=LABEL_NAME_MAX_LENGTH,
        description="Label name",
    )
    color: str = Field(
        default=DEFAULT_LABEL_COLOR,
        description="Hex color code (e.g. #3B82F6 or #FFF)",
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: str) -> str:
        return validate_not_blank_name(v)

    @field_validator("color")
    @classmethod
    def validate_color_format(cls, v: str) -> str:
        return validate_hex_color(v)


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
        return validate_not_blank_name(v)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError(MSG_CANNOT_BE_NULL.format(field="Color"))
        return validate_hex_color(v)


class LabelResponse(LabelBase):
    id: int
    project_id: int

    model_config = ConfigDict(from_attributes=True)
