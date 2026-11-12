from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.deps import CurrentUser, get_workspace_service
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberAdd,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.services.workspace_service import WorkspaceService

router = APIRouter()


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
    description="Create a workspace. The creator is automatically assigned as OWNER.",
)
@router.post(
    "/",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_workspace(
    ws_in: WorkspaceCreate,
    current_user: CurrentUser,
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceResponse:
    """Create a new workspace owned by the authenticated user."""
    return await workspace_service.create_workspace(user_id=current_user.id, ws_in=ws_in)


@router.get(
    "",
    response_model=list[WorkspaceResponse],
    status_code=status.HTTP_200_OK,
    summary="List workspaces",
    description="Retrieve all workspaces where the current user is an owner or member.",
)
@router.get(
    "/",
    response_model=list[WorkspaceResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def list_workspaces(
    current_user: CurrentUser,
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> list[WorkspaceResponse]:
    """List all workspaces accessible to the authenticated user."""
    return await workspace_service.list_my_workspaces(user_id=current_user.id)


@router.get(
    "/{id}",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get workspace details",
    description="Get details and member list of a workspace (members only).",
    responses={
        403: {"description": "Access denied (not a member)"},
        404: {"description": "Workspace not found"},
    },
)
async def get_workspace(
    id: Annotated[int, Path(ge=1, description="Workspace ID")],
    current_user: CurrentUser,
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceResponse:
    """Retrieve workspace details and members."""
    return await workspace_service.get_workspace(workspace_id=id, current_user=current_user)


@router.patch(
    "/{id}",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update workspace",
    description="Update workspace attributes. Restricted to workspace OWNER.",
    responses={
        403: {"description": "Permission denied (OWNER role required)"},
        404: {"description": "Workspace not found"},
        422: {"description": "Validation error on field update"},
    },
)
async def update_workspace(
    id: Annotated[int, Path(ge=1, description="Workspace ID")],
    ws_in: WorkspaceUpdate,
    current_user: CurrentUser,
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceResponse:
    """Update workspace name (OWNER only)."""
    return await workspace_service.update_workspace(workspace_id=id, current_user=current_user, ws_in=ws_in)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workspace",
    description="Permanently delete a workspace. Restricted to workspace OWNER.",
    responses={
        403: {"description": "Permission denied (OWNER role required)"},
        404: {"description": "Workspace not found"},
    },
)
async def delete_workspace(
    id: Annotated[int, Path(ge=1, description="Workspace ID")],
    current_user: CurrentUser,
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> None:
    """Permanently delete a workspace (OWNER only)."""
    await workspace_service.delete_workspace(workspace_id=id, current_user=current_user)


@router.post(
    "/{id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add workspace member",
    description="Invite/add a user to the workspace with specified role (OWNER only).",
    responses={
        400: {"description": "Owner already has full permissions"},
        403: {"description": "Permission denied (OWNER role required)"},
        404: {"description": "Workspace or target user not found"},
    },
)
async def add_workspace_member(
    id: Annotated[int, Path(ge=1, description="Workspace ID")],
    member_in: WorkspaceMemberAdd,
    current_user: CurrentUser,
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceMemberResponse:
    """Add a member to the workspace with specified role (OWNER only)."""
    return await workspace_service.add_member(workspace_id=id, current_user=current_user, member_in=member_in)


@router.delete(
    "/{id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove workspace member",
    description="Remove a member from the workspace (OWNER only). Cannot remove owner.",
    responses={
        400: {"description": "Cannot remove the workspace owner"},
        403: {"description": "Permission denied (OWNER role required)"},
        404: {"description": "Workspace or member not found"},
    },
)
async def remove_workspace_member(
    id: Annotated[int, Path(ge=1, description="Workspace ID")],
    user_id: Annotated[int, Path(ge=1, description="Target user ID to remove")],
    current_user: CurrentUser,
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> None:
    """Remove a member from the workspace (OWNER only)."""
    await workspace_service.remove_member(workspace_id=id, current_user=current_user, target_user_id=user_id)
