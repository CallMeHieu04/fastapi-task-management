from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Path, status

from app.api.deps import (
    TaskFilterParams,
    get_current_user,
    get_label_service,
    get_project_service,
    get_task_service,
)
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.label import LabelCreate, LabelResponse
from app.schemas.project import ProjectResponse, ProjectUpdate
from app.schemas.task import TaskCreate, TaskResponse
from app.services.label_service import LabelService
from app.services.project_service import ProjectService
from app.services.task_service import TaskService

router = APIRouter()


@router.get(
    "/{id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project details by ID",
)
async def get_project(
    id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """Retrieve details of a single project."""
    return await service.get_project(project_id=id, current_user=current_user)


@router.patch(
    "/{id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Update project details",
)
async def update_project(
    id: Annotated[int, Path(ge=1)],
    project_in: ProjectUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """Update project name, description or status."""
    return await service.update_project(project_id=id, current_user=current_user, project_in=project_in)


@router.patch(
    "/{id}/archive",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive project",
)
async def archive_project(
    id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """Quickly set project status to ARCHIVED."""
    return await service.archive_project(project_id=id, current_user=current_user)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project (OWNER only)",
)
async def delete_project(
    id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> None:
    """Delete project permanently (restricted to workspace OWNER)."""
    await service.delete_project(project_id=id, current_user=current_user)


# Task endpoints under project
@router.get(
    "/{id}/tasks",
    response_model=PaginatedResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    summary="List project tasks (with filtering, pagination & Redis caching)",
)
async def list_project_tasks(
    id: Annotated[int, Path(ge=1)],
    filters: Annotated[TaskFilterParams, Depends()],
    current_user: Annotated[User, Depends(get_current_user)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> PaginatedResponse[TaskResponse]:
    """Retrieve tasks with optional filters (status, priority, assignee) cached in Redis."""
    return await task_service.list_tasks(
        project_id=id,
        current_user=current_user,
        status_filter=filters.status,
        priority_filter=filters.priority,
        assignee_id=filters.assignee_id,
        page=filters.page,
        page_size=filters.limit,
    )


@router.post(
    "/{id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task in project",
)
async def create_project_task(
    id: Annotated[int, Path(ge=1)],
    task_in: TaskCreate,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    """Create a task in the project. If assignee is given, triggers async email notification."""
    return await task_service.create_task(
        project_id=id,
        current_user=current_user,
        task_in=task_in,
        background_tasks=background_tasks,
    )


# Label endpoints under project
@router.get(
    "/{id}/labels",
    response_model=list[LabelResponse],
    status_code=status.HTTP_200_OK,
    summary="List all labels in project",
)
async def list_project_labels(
    id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    label_service: Annotated[LabelService, Depends(get_label_service)],
) -> list[LabelResponse]:
    """Retrieve all labels created for this project."""
    return await label_service.list_labels(project_id=id, current_user=current_user)


@router.post(
    "/{id}/labels",
    response_model=LabelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new label for project",
)
async def create_project_label(
    id: Annotated[int, Path(ge=1)],
    label_in: LabelCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    label_service: Annotated[LabelService, Depends(get_label_service)],
) -> LabelResponse:
    """Create a color-coded label inside this project."""
    return await label_service.create_label(
        project_id=id, current_user=current_user, label_in=label_in
    )
