from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.deps import CurrentUser, get_label_service
from app.schemas.label import LabelResponse, LabelUpdate
from app.services.label_service import LabelService

router = APIRouter()


@router.patch(
    "/{id}",
    response_model=LabelResponse,
    status_code=status.HTTP_200_OK,
    summary="Update label",
    description="Update label name or hex color (Workspace OWNER or EDITOR only).",
    responses={
        403: {"description": "Permission denied (OWNER or EDITOR role required)"},
        404: {"description": "Label not found"},
        422: {"description": "Validation error"},
    },
)
async def update_label(
    id: Annotated[int, Path(ge=1, description="Label ID")],
    label_in: LabelUpdate,
    current_user: CurrentUser,
    label_service: Annotated[LabelService, Depends(get_label_service)],
) -> LabelResponse:
    """Partially update a label's name or color."""
    return await label_service.update_label(label_id=id, current_user=current_user, label_in=label_in)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete label",
    description="Delete a label and detach it from all associated tasks (Workspace OWNER or EDITOR only).",
    responses={
        403: {"description": "Permission denied (OWNER or EDITOR role required)"},
        404: {"description": "Label not found"},
    },
)
async def delete_label(
    id: Annotated[int, Path(ge=1, description="Label ID")],
    current_user: CurrentUser,
    label_service: Annotated[LabelService, Depends(get_label_service)],
) -> None:
    """Delete a label by ID."""
    await label_service.delete_label(label_id=id, current_user=current_user)
