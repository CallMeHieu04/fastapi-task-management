from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.deps import (
    get_current_user,
    get_project_service,
    get_workspace_service,
)
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectResponse
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberAdd,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.services.project_service import ProjectService
from app.services.workspace_service import WorkspaceService

router = APIRouter()


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
)
@router.post(
    "/",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_workspace(
    ws_in: WorkspaceCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceResponse:
    """Create a new workspace. The creator automatically receives the OWNER role."""
    return await service.create_workspace(user_id=current_user.id, ws_in=ws_in)


@router.get(
    "",
    response_model=list[WorkspaceResponse],
    status_code=status.HTTP_200_OK,
    summary="List all workspaces I belong to",
)
@router.get(
    "/",
    response_model=list[WorkspaceResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def list_workspaces(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> list[WorkspaceResponse]:
    """Retrieve all workspaces where the current user is an owner or member."""
    return await service.list_my_workspaces(user_id=current_user.id)


@router.get(
    "/{id}",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get workspace details by ID",
)
async def get_workspace(
    id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceResponse:
    """Retrieve details and members of a workspace (members only)."""
    return await service.get_workspace(workspace_id=id, current_user=current_user)


@router.patch(
    "/{id}",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update workspace (OWNER only)",
)
async def update_workspace(
    id: Annotated[int, Path(ge=1)],
    ws_in: WorkspaceUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceResponse:
    """Update workspace name (restricted to workspace OWNER)."""
    return await service.update_workspace(workspace_id=id, current_user=current_user, ws_in=ws_in)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workspace (OWNER only)",
)
async def delete_workspace(
    id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> None:
    """Permanently delete a workspace and its projects (restricted to workspace OWNER)."""
    await service.delete_workspace(workspace_id=id, current_user=current_user)


@router.post(
    "/{id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite/add a member to workspace (OWNER only)",
)
async def add_workspace_member(
    id: Annotated[int, Path(ge=1)],
    member_in: WorkspaceMemberAdd,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceMemberResponse:
    """Add or invite a member to the workspace with specified role (OWNER only)."""
    return await service.add_member(workspace_id=id, current_user=current_user, member_in=member_in)


@router.delete(
    "/{id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from workspace (OWNER only)",
)
async def remove_workspace_member(
    id: Annotated[int, Path(ge=1)],
    user_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> None:
    """Remove a member from the workspace (restricted to workspace OWNER)."""
    await service.remove_member(workspace_id=id, current_user=current_user, target_user_id=user_id)


# Project sub-routes under workspace
@router.post(
    "/{id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project in workspace (OWNER/EDITOR)",
)
async def create_project_in_workspace(
    id: Annotated[int, Path(ge=1)],
    project_in: ProjectCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    """Create a new project inside the workspace."""
    return await project_service.create_project(
        workspace_id=id, current_user=current_user, project_in=project_in
    )


@router.get(
    "/{id}/projects",
    response_model=list[ProjectResponse],
    status_code=status.HTTP_200_OK,
    summary="List all projects in workspace",
)
async def list_workspace_projects(
    id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> list[ProjectResponse]:
    """List all projects within the given workspace."""
    return await project_service.list_projects(workspace_id=id, current_user=current_user)
