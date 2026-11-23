from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.deps import CurrentUser, get_label_service
from app.schemas.label import LabelCreate, LabelResponse, LabelUpdate
from app.schemas.task import TaskResponse
from app.services.label_service import LabelService

router = APIRouter()


@router.post(
    "/projects/{id}/labels",
    response_model=LabelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create label in project",
    description="Create a new label for this project (Workspace OWNER or EDITOR only).",
    responses={
        400: {"description": "Project archived"},
        403: {"description": "Permission denied (OWNER or EDITOR role required)"},
        404: {"description": "Project not found"},
        409: {"description": "Label with this name already exists in project"},
        422: {"description": "Validation error"},
    },
)
async def create_project_label(
    id: Annotated[int, Path(ge=1, description="Project ID")],
    label_in: LabelCreate,
    current_user: CurrentUser,
    label_service: Annotated[LabelService, Depends(get_label_service)],
) -> LabelResponse:
    """Create a new label under the specified project."""
    return await label_service.create_label(project_id=id, current_user=current_user, label_in=label_in)


@router.get(
    "/projects/{id}/labels",
    response_model=list[LabelResponse],
    status_code=status.HTTP_200_OK,
    summary="List project labels",
    description="Retrieve all labels created for this project (Workspace members only).",
    responses={
        403: {"description": "Access denied (not a workspace member)"},
        404: {"description": "Project not found"},
    },
)
async def list_project_labels(
    id: Annotated[int, Path(ge=1, description="Project ID")],
    current_user: CurrentUser,
    label_service: Annotated[LabelService, Depends(get_label_service)],
) -> list[LabelResponse]:
    """Retrieve all labels belonging to the project."""
    return await label_service.list_labels(project_id=id, current_user=current_user)


@router.post(
    "/tasks/{id}/labels/{label_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Attach label to task",
    description="Attach an existing project label to a task (Workspace OWNER or EDITOR only).",
    responses={
        400: {"description": "Project archived or invalid task"},
        403: {"description": "Permission denied (OWNER or EDITOR role required)"},
        404: {"description": "Task or label not found"},
        409: {"description": "Label already attached to task"},
    },
)
async def attach_label_to_task(
    id: Annotated[int, Path(ge=1, description="Task ID")],
    label_id: Annotated[int, Path(ge=1, description="Label ID")],
    current_user: CurrentUser,
    label_service: Annotated[LabelService, Depends(get_label_service)],
) -> TaskResponse:
    """Attach a label to the task."""
    return await label_service.attach_label_to_task(task_id=id, label_id=label_id, current_user=current_user)


@router.delete(
    "/tasks/{id}/labels/{label_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Detach label from task",
    description="Remove a label from a task (Workspace OWNER or EDITOR only).",
    responses={
        400: {"description": "Project archived or invalid task"},
        403: {"description": "Permission denied (OWNER or EDITOR role required)"},
        404: {"description": "Task, label not found or label not attached"},
    },
)
async def detach_label_from_task(
    id: Annotated[int, Path(ge=1, description="Task ID")],
    label_id: Annotated[int, Path(ge=1, description="Label ID")],
    current_user: CurrentUser,
    label_service: Annotated[LabelService, Depends(get_label_service)],
) -> TaskResponse:
    """Detach a label from the task."""
    return await label_service.detach_label_from_task(task_id=id, label_id=label_id, current_user=current_user)


@router.patch(
    "/labels/{id}",
    response_model=LabelResponse,
    status_code=status.HTTP_200_OK,
    summary="Update label",
    description="Update label name or hex color (Workspace OWNER or EDITOR only).",
    responses={
        400: {"description": "Project archived"},
        403: {"description": "Permission denied (OWNER or EDITOR role required)"},
        404: {"description": "Label not found"},
        409: {"description": "Label with this name already exists in project"},
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
    "/labels/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete label",
    description="Delete a label and detach it from all associated tasks (Workspace OWNER or EDITOR only).",
    responses={
        400: {"description": "Project archived"},
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
