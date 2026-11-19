from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.deps import CurrentUser, PaginationParams, get_project_service
from app.schemas.common import PaginatedResponse
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter()


@router.post(
    "/workspaces/{id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project in workspace",
    description="Create a project in the specified workspace (OWNER or EDITOR only).",
    responses={
        403: {"description": "Permission denied (OWNER or EDITOR role required)"},
        404: {"description": "Workspace not found"},
    },
)
async def create_workspace_project(
    id: Annotated[int, Path(ge=1, description="Workspace ID")],
    project_in: ProjectCreate,
    current_user: CurrentUser,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """Create a new project within the workspace."""
    return await project_service.create_project(workspace_id=id, current_user=current_user, project_in=project_in)


@router.get(
    "/workspaces/{id}/projects",
    response_model=PaginatedResponse[ProjectResponse],
    status_code=status.HTTP_200_OK,
    summary="List workspace projects",
    description="Retrieve paginated projects belonging to the workspace (Workspace members only).",
    responses={
        403: {"description": "Access denied (not a workspace member)"},
        404: {"description": "Workspace not found"},
    },
)
async def list_workspace_projects(
    id: Annotated[int, Path(ge=1, description="Workspace ID")],
    pagination: Annotated[PaginationParams, Depends()],
    current_user: CurrentUser,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> PaginatedResponse[ProjectResponse]:
    """Retrieve paginated projects for a workspace."""
    return await project_service.list_projects(
        workspace_id=id,
        current_user=current_user,
        page=pagination.page,
        limit=pagination.limit,
    )


@router.get(
    "/projects/{id}",
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
    "/projects/{id}",
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
    "/projects/{id}",
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
