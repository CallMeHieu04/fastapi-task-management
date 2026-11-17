from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.deps import CurrentUser, TaskFilterParams, get_project_service, get_task_service
from app.schemas.common import PaginatedResponse
from app.schemas.project import ProjectResponse, ProjectUpdate
from app.schemas.task import TaskCreate, TaskResponse
from app.services.project_service import ProjectService
from app.services.task_service import TaskService

router = APIRouter()


@router.get(
    "/{id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project details",
    description="Retrieve details of a project (Workspace members only).",
    responses={
        403: {"description": "Access denied (not a workspace member)"},
        404: {"description": "Project not found"},
    },
)
async def get_project(
    id: Annotated[int, Path(ge=1, description="Project ID")],
    current_user: CurrentUser,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """Retrieve details of a single project."""
    return await project_service.get_project(project_id=id, current_user=current_user)


@router.patch(
    "/{id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Update project",
    description="Update project name, description, or status (Workspace OWNER or EDITOR only).",
    responses={
        403: {"description": "Permission denied (OWNER or EDITOR role required)"},
        404: {"description": "Project not found"},
        422: {"description": "Validation error"},
    },
)
async def update_project(
    id: Annotated[int, Path(ge=1, description="Project ID")],
    project_in: ProjectUpdate,
    current_user: CurrentUser,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """Partially update a project."""
    return await project_service.update_project(project_id=id, current_user=current_user, project_in=project_in)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
    description="Permanently delete project and its associated tasks (Workspace OWNER or EDITOR only).",
    responses={
        403: {"description": "Permission denied (OWNER or EDITOR role required)"},
        404: {"description": "Project not found"},
    },
)
async def delete_project(
    id: Annotated[int, Path(ge=1, description="Project ID")],
    current_user: CurrentUser,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> None:
    """Delete a project by ID."""
    await project_service.delete_project(project_id=id, current_user=current_user)


@router.post(
    "/{id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create task in project",
    description="Create a task associated with this project (Workspace OWNER or EDITOR only).",
    responses={
        403: {"description": "Permission denied (OWNER or EDITOR role required)"},
        404: {"description": "Project not found"},
    },
)
async def create_project_task(
    id: Annotated[int, Path(ge=1, description="Project ID")],
    task_in: TaskCreate,
    current_user: CurrentUser,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    """Create a new task within the specified project."""
    return await task_service.create_project_task(project_id=id, current_user=current_user, task_in=task_in)


@router.get(
    "/{id}/tasks",
    response_model=PaginatedResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    summary="List project tasks",
    description="Retrieve paginated tasks for this project (Workspace members only).",
    responses={
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
        current_user=current_user,
        status=filters.status,
        priority=filters.priority,
        search=filters.search,
        page=filters.page,
        page_size=filters.limit,
    )
