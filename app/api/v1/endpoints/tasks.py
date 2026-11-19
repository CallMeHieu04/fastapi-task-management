from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.deps import CurrentUser, TaskFilterParams, get_task_service
from app.schemas.common import PaginatedResponse
from app.schemas.task import ProjectTaskCreate, TaskCreate, TaskResponse, TaskUpdate
from app.services.task_service import TaskService

router = APIRouter()


@router.post(
    "/projects/{id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create task in project",
    description="Create a task associated with this project (Workspace OWNER or EDITOR only).",
    responses={
        400: {"description": "Project archived or invalid assignee"},
        401: {"description": "Authentication required"},
        403: {"description": "Permission denied (OWNER or EDITOR role required)"},
        404: {"description": "Project not found"},
    },
)
async def create_project_task(
    id: Annotated[int, Path(ge=1, description="Project ID")],
    task_in: ProjectTaskCreate,
    current_user: CurrentUser,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    """Create a new task within the specified project."""
    return await task_service.create_project_task(project_id=id, current_user=current_user, task_in=task_in)


@router.get(
    "/projects/{id}/tasks",
    response_model=PaginatedResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    summary="List project tasks",
    description="Retrieve paginated tasks for this project (Workspace members only).",
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Access denied (not a workspace member)"},
        404: {"description": "Project not found"},
    },
)
async def list_project_tasks(
    id: Annotated[int, Path(ge=1, description="Project ID")],
    filters: Annotated[TaskFilterParams, Depends()],
    current_user: CurrentUser,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> PaginatedResponse[TaskResponse]:
    """Retrieve tasks belonging to the project."""
    return await task_service.list_project_tasks(
        project_id=id,
        filters=filters,
        current_user=current_user,
    )


@router.get(
    "/tasks",
    response_model=PaginatedResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    summary="List all tasks",
    description="Retrieve paginated tasks with optional status, priority, project_id, and keyword filtering.",
    responses={
        401: {"description": "Authentication required"},
    },
)
async def list_tasks(
    filters: Annotated[TaskFilterParams, Depends()],
    current_user: CurrentUser,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> PaginatedResponse[TaskResponse]:
    return await service.list_tasks(filters=filters, current_user=current_user)


@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
    description="Create a task with validated title, optional description, priority, and project attachment.",
    responses={
        400: {"description": "Project archived or invalid assignee"},
        401: {"description": "Authentication required"},
        403: {"description": "Permission denied"},
        404: {"description": "Project or assignee not found"},
    },
)
async def create_task(
    task_in: TaskCreate,
    current_user: CurrentUser,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    return await service.create_task(task_in=task_in, current_user=current_user)


@router.get(
    "/tasks/{id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Get task details",
    description="Retrieve details of a single task by its integer identifier.",
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Task not found"},
    },
)
async def get_task(
    id: Annotated[int, Path(ge=1, description="The ID of the task")],
    current_user: CurrentUser,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    return await service.get_task(task_id=id, current_user=current_user)


@router.patch(
    "/tasks/{id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update a task",
    description="Update task fields. Explicit null on required fields is rejected with 422.",
    responses={
        400: {"description": "Project archived or invalid assignee"},
        401: {"description": "Authentication required"},
        403: {"description": "Permission denied"},
        404: {"description": "Task not found"},
        422: {"description": "Validation error"},
    },
)
async def update_task(
    id: Annotated[int, Path(ge=1, description="The ID of the task")],
    task_in: TaskUpdate,
    current_user: CurrentUser,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    return await service.update_task(task_id=id, task_in=task_in, current_user=current_user)


@router.delete(
    "/tasks/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
    description="Delete a task by ID. Returns 204 No Content.",
    responses={
        400: {"description": "Project archived"},
        401: {"description": "Authentication required"},
        403: {"description": "Permission denied"},
        404: {"description": "Task not found"},
    },
)
async def delete_task(
    id: Annotated[int, Path(ge=1, description="The ID of the task")],
    current_user: CurrentUser,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> None:
    await service.delete_task(task_id=id, current_user=current_user)
