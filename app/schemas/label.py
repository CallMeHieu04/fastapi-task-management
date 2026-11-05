from pydantic import BaseModel, ConfigDict, Field


class LabelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(
        default="#3B82F6",
        pattern=r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$",
        description="Hex color code, e.g. #FF5733",
    )

    model_config = ConfigDict(str_strip_whitespace=True)


class LabelCreate(LabelBase):
    pass


class LabelResponse(LabelBase):
    id: int
    project_id: int

    model_config = ConfigDict(from_attributes=True)
