from app.core.constants import (
    MSG_CANNOT_REMOVE_OWNER,
    MSG_MEMBER_NOT_FOUND,
    MSG_OWNER_ALREADY_MEMBER,
    MSG_OWNER_REQUIRED,
    MSG_USER_NOT_FOUND,
    MSG_VIEWER_CANNOT_MODIFY,
    MSG_WORKSPACE_ACCESS_DENIED,
    MSG_WORKSPACE_NOT_FOUND,
)
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
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
    def __init__(self, workspace_repo: WorkspaceRepository, user_repo: UserRepository) -> None:
        self.workspace_repo = workspace_repo
        self.user_repo = user_repo

    async def check_workspace_access(
        self,
        workspace_id: int,
        current_user: User,
        required_role: WorkspaceMemberRole | None = None,
    ) -> bool:
        """Helper to verify workspace membership and role hierarchy."""
        if current_user.role == UserRole.ADMIN:
            return True

        member = await self.workspace_repo.get_member(workspace_id, current_user.id)
        if not member:
            raise ForbiddenException(MSG_WORKSPACE_ACCESS_DENIED)

        if required_role == WorkspaceMemberRole.OWNER and member.role != WorkspaceMemberRole.OWNER:
            raise ForbiddenException(MSG_OWNER_REQUIRED)

        if required_role == WorkspaceMemberRole.EDITOR and member.role == WorkspaceMemberRole.VIEWER:
            raise ForbiddenException(MSG_VIEWER_CANNOT_MODIFY)

        return True

    async def create_workspace(self, user_id: int, ws_in: WorkspaceCreate) -> WorkspaceResponse:
        workspace = await self.workspace_repo.create(name=ws_in.name, owner_id=user_id)
        return self._format_response(workspace)

    async def list_my_workspaces(self, user_id: int) -> list[WorkspaceResponse]:
        workspaces = await self.workspace_repo.list_by_user(user_id)
        return [self._format_response(w) for w in workspaces]

    async def get_workspace(self, workspace_id: int, current_user: User) -> WorkspaceResponse:
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(MSG_WORKSPACE_NOT_FOUND.format(id=workspace_id))
        await self.check_workspace_access(workspace_id, current_user)
        return self._format_response(workspace)

    async def update_workspace(
        self, workspace_id: int, current_user: User, ws_in: WorkspaceUpdate
    ) -> WorkspaceResponse:
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(MSG_WORKSPACE_NOT_FOUND.format(id=workspace_id))
        await self.check_workspace_access(workspace_id, current_user, required_role=WorkspaceMemberRole.OWNER)

        if ws_in.name:
            workspace = await self.workspace_repo.update(workspace, ws_in.name)
        return self._format_response(workspace)

    async def delete_workspace(self, workspace_id: int, current_user: User) -> None:
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(MSG_WORKSPACE_NOT_FOUND.format(id=workspace_id))
        await self.check_workspace_access(workspace_id, current_user, required_role=WorkspaceMemberRole.OWNER)
        await self.workspace_repo.delete(workspace)

    async def add_member(
        self, workspace_id: int, current_user: User, member_in: WorkspaceMemberAdd
    ) -> WorkspaceMemberResponse:
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(MSG_WORKSPACE_NOT_FOUND.format(id=workspace_id))
        await self.check_workspace_access(workspace_id, current_user, required_role=WorkspaceMemberRole.OWNER)

        target_user = None
        if member_in.user_id:
            target_user = await self.user_repo.get_by_id(member_in.user_id)
        elif member_in.email:
            target_user = await self.user_repo.get_by_email(member_in.email)

        if not target_user:
            raise NotFoundException(MSG_USER_NOT_FOUND.format(id=member_in.user_id or member_in.email))

        if target_user.id == workspace.owner_id:
            raise BadRequestException(MSG_OWNER_ALREADY_MEMBER)

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

    async def remove_member(self, workspace_id: int, current_user: User, target_user_id: int) -> None:
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(MSG_WORKSPACE_NOT_FOUND.format(id=workspace_id))
        await self.check_workspace_access(workspace_id, current_user, required_role=WorkspaceMemberRole.OWNER)

        if target_user_id == workspace.owner_id:
            raise BadRequestException(MSG_CANNOT_REMOVE_OWNER)

        removed = await self.workspace_repo.remove_member(workspace_id, target_user_id)
        if not removed:
            raise NotFoundException(MSG_MEMBER_NOT_FOUND)

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
