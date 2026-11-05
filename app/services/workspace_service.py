
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole, WorkspaceMemberRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberAdd,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)


class WorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.workspace_repo = WorkspaceRepository(session)
        self.user_repo = UserRepository(session)

    async def _check_workspace_access(
        self, workspace_id: int, current_user: User, required_role: WorkspaceMemberRole | None = None
    ):
        """Helper to verify workspace membership and role hierarchy."""
        if current_user.role == UserRole.ADMIN:
            return True

        member = await self.workspace_repo.get_member(workspace_id, current_user.id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this workspace.",
            )

        if required_role == WorkspaceMemberRole.OWNER and member.role != WorkspaceMemberRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace OWNER can perform this action.",
            )

        if required_role == WorkspaceMemberRole.EDITOR and member.role == WorkspaceMemberRole.VIEWER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Workspace VIEWERS are not permitted to modify this resource.",
            )

        return member

    async def create_workspace(self, user_id: int, ws_in: WorkspaceCreate) -> WorkspaceResponse:
        workspace = await self.workspace_repo.create(name=ws_in.name, owner_id=user_id)
        return self._format_response(workspace)

    async def list_my_workspaces(self, user_id: int) -> list[WorkspaceResponse]:
        workspaces = await self.workspace_repo.list_by_user(user_id)
        return [self._format_response(w) for w in workspaces]

    async def get_workspace(self, workspace_id: int, current_user: User) -> WorkspaceResponse:
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace #{workspace_id} not found.",
            )
        await self._check_workspace_access(workspace_id, current_user)
        return self._format_response(workspace)

    async def update_workspace(
        self, workspace_id: int, current_user: User, ws_in: WorkspaceUpdate
    ) -> WorkspaceResponse:
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace #{workspace_id} not found.",
            )
        await self._check_workspace_access(workspace_id, current_user, required_role=WorkspaceMemberRole.OWNER)

        if ws_in.name:
            workspace = await self.workspace_repo.update(workspace, ws_in.name)
        return self._format_response(workspace)

    async def delete_workspace(self, workspace_id: int, current_user: User) -> None:
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace #{workspace_id} not found.",
            )
        await self._check_workspace_access(workspace_id, current_user, required_role=WorkspaceMemberRole.OWNER)
        await self.workspace_repo.delete(workspace)

    async def add_member(
        self, workspace_id: int, current_user: User, member_in: WorkspaceMemberAdd
    ) -> WorkspaceMemberResponse:
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace #{workspace_id} not found.",
            )
        await self._check_workspace_access(workspace_id, current_user, required_role=WorkspaceMemberRole.OWNER)

        target_user = None
        if member_in.user_id:
            target_user = await self.user_repo.get_by_id(member_in.user_id)
        elif member_in.email:
            target_user = await self.user_repo.get_by_email(member_in.email)

        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User to invite was not found.",
            )

        if target_user.id == workspace.owner_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The workspace owner already has full OWNER permissions.",
            )

        member = await self.workspace_repo.add_member(
            workspace_id=workspace_id,
            user_id=target_user.id,
            role=member_in.role,
        )
        return WorkspaceMemberResponse(
            user_id=target_user.id,
            email=target_user.email,
            full_name=target_user.full_name,
            role=member.role,
        )

    async def remove_member(
        self, workspace_id: int, current_user: User, target_user_id: int
    ) -> None:
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace #{workspace_id} not found.",
            )
        await self._check_workspace_access(workspace_id, current_user, required_role=WorkspaceMemberRole.OWNER)

        if target_user_id == workspace.owner_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the owner from their own workspace.",
            )

        removed = await self.workspace_repo.remove_member(workspace_id, target_user_id)
        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in workspace.",
            )

    def _format_response(self, workspace) -> WorkspaceResponse:
        members_data = []
        if workspace.members:
            for m in workspace.members:
                members_data.append(
                    WorkspaceMemberResponse(
                        user_id=m.user_id,
                        email=m.user.email if m.user else None,
                        full_name=m.user.full_name if m.user else None,
                        role=m.role,
                    )
                )
        return WorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            owner_id=workspace.owner_id,
            created_at=workspace.created_at,
            members=members_data,
        )
