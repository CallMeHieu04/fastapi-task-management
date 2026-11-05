from pydantic import ConfigDict, Field, field_validator

from app.core.constants import (
    HEX_COLOR_REGEX,
    LABEL_NAME_MAX_LENGTH,
    LABEL_NAME_MIN_LENGTH,
    MSG_CANNOT_BE_BLANK,
)
from app.schemas.common import BaseAppModel


class LabelBase(BaseAppModel):
    name: str = Field(
        ...,
        min_length=LABEL_NAME_MIN_LENGTH,
        max_length=LABEL_NAME_MAX_LENGTH,
    )
    color: str = Field(
        default="#3B82F6",
        pattern=HEX_COLOR_REGEX,
        description="Hex color code, e.g. #FF5733",
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(MSG_CANNOT_BE_BLANK.format(field="Label name"))
        return v.strip()


class LabelCreate(LabelBase):
    pass


class LabelResponse(LabelBase):
    id: int
    project_id: int

    model_config = ConfigDict(from_attributes=True)
