from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Metadata describing the paginated dataset."""

    total: int = Field(..., description="Total number of items matching criteria", ge=0)
    page: int = Field(..., description="Current page number (1-indexed)", ge=1)
    page_size: int = Field(..., description="Items per page", ge=1)
    total_pages: int = Field(..., description="Total pages available", ge=0)


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized paginated envelope."""

    items: list[T]
    meta: PaginationMeta


class MessageResponse(BaseModel):
    """Generic status/message response."""

    message: str
    detail: str | None = None

