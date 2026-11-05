from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BaseAppModel(BaseModel):
    """Base schema enforcing automatic whitespace stripping for all string fields."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )


class PaginationMeta(BaseAppModel):
    """Metadata describing the paginated dataset."""

    total: int = Field(..., description="Total number of items matching criteria", ge=0)
    page: int = Field(..., description="Current page number (1-indexed)", ge=1)
    page_size: int = Field(..., description="Items per page", ge=1)
    total_pages: int = Field(..., description="Total pages available", ge=0)


class PaginatedResponse(BaseAppModel, Generic[T]):
    """Standardized paginated envelope."""

    items: list[T]
    meta: PaginationMeta


class MessageResponse(BaseAppModel):
    """Generic status/message response."""

    message: str
    detail: str | None = None
