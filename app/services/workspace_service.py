import math

from fastapi import BackgroundTasks

from app.core.cache import CacheService
from app.core.constants import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MSG_CANNOT_REMOVE_OWNER,
    MSG_MEMBER_ALREADY_EXISTS,
    MSG_MEMBER_NOT_FOUND,
    MSG_OWNER_ALREADY_MEMBER,
    MSG_OWNER_REQUIRED,
    MSG_USER_NOT_FOUND,
    MSG_VIEWER_CANNOT_MODIFY,
    MSG_WORKSPACE_NOT_FOUND,
)
from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.models.enums import UserRole, WorkspaceMemberRole
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberAdd,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.services.notification_service import NotificationService


class WorkspaceService:
    """Service encapsulating Workspace domain logic, membership, and RBAC authorization."""

    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        user_repo: UserRepository,
        cache_service: CacheService | None = None,
    ) -> None:
        self.workspace_repo = workspace_repo
        self.user_repo = user_repo
        self.cache = cache_service

    async def check_workspace_access(
        self,
        workspace_id: int,
        current_user: User,
        required_role: WorkspaceMemberRole | None = None,
    ) -> bool:
        """Verify that current user is an authorized member with sufficient privileges."""
        if current_user.role == UserRole.ADMIN:
            return True

        member = await self.workspace_repo.get_member(workspace_id, current_user.id)
        if not member:
            # Outsiders receive 404 to avoid leaking workspace existence
            raise NotFoundException(MSG_WORKSPACE_NOT_FOUND.format(id=workspace_id))

        if required_role == WorkspaceMemberRole.OWNER and member.role != WorkspaceMemberRole.OWNER:
            raise ForbiddenException(MSG_OWNER_REQUIRED)

        if required_role == WorkspaceMemberRole.EDITOR and member.role == WorkspaceMemberRole.VIEWER:
            raise ForbiddenException(MSG_VIEWER_CANNOT_MODIFY)

        return True

    async def get_user_role(self, workspace_id: int, user_id: int) -> WorkspaceMemberRole | None:
        """Get the member role of a user in a workspace, or None if not a member."""
        member = await self.workspace_repo.get_member(workspace_id, user_id)
        return member.role if member else None

    async def is_workspace_owner(self, workspace_id: int, user_id: int) -> bool:
        """Check if user has OWNER role in the workspace."""
        member = await self.workspace_repo.get_member(workspace_id, user_id)
        return member is not None and member.role == WorkspaceMemberRole.OWNER

    def _format_response(self, workspace: Workspace) -> WorkspaceResponse:
        members_data = []
        if workspace.members:
            for m in workspace.members:
                members_data.append(
                    WorkspaceMemberResponse(
                        user_id=m.user_id,
                        email=m.user.email,
                        full_name=m.user.full_name,
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

    async def create_workspace(self, user_id: int, ws_in: WorkspaceCreate) -> WorkspaceResponse:
        """Create a new workspace owned by the current user."""
        workspace = await self.workspace_repo.create_workspace(name=ws_in.name, owner_id=user_id)
        if self.cache:
            await self.cache.delete_pattern("workspaces:user:*")
        return self._format_response(workspace)

    async def list_my_workspaces(
        self,
        user_id: int,
        page: int = DEFAULT_PAGE,
        limit: int = DEFAULT_PAGE_SIZE,
        search: str | None = None,
    ) -> PaginatedResponse[WorkspaceResponse]:
        """List paginated workspaces the user owns or belongs to with optional name search."""
        cache_key = f"workspaces:user:{user_id}:p{page}:l{limit}:q{search}"
        if self.cache:
            cached = await self.cache.get_json(cache_key)
            if cached:
                return PaginatedResponse[WorkspaceResponse].model_validate(cached)

        workspaces, total = await self.workspace_repo.list_by_user(
            user_id=user_id,
            page=page,
            limit=limit,
            search=search,
        )
        total_pages = math.ceil(total / limit) if total > 0 else 0

        items = [
            WorkspaceResponse(
                id=w.id,
                name=w.name,
                owner_id=w.owner_id,
                created_at=w.created_at,
                members=[],
            )
            for w in workspaces
        ]
        result = PaginatedResponse(
            items=items,
            meta=PaginationMeta(
                total=total,
                page=page,
                page_size=limit,
                total_pages=total_pages,
            ),
        )
        if self.cache:
            await self.cache.set_json(cache_key, result.model_dump())
        return result

    async def get_workspace(self, workspace_id: int, current_user: User) -> WorkspaceResponse:
        """Get details and members of a workspace."""
        await self.check_workspace_access(workspace_id, current_user)

        cache_key = f"workspaces:detail:{workspace_id}"
        if self.cache:
            cached = await self.cache.get_json(cache_key)
            if cached:
                return WorkspaceResponse.model_validate(cached)

        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(MSG_WORKSPACE_NOT_FOUND.format(id=workspace_id))

        res = self._format_response(workspace)
        if self.cache:
            await self.cache.set_json(cache_key, res.model_dump())
        return res

    async def update_workspace(
        self,
        workspace_id: int,
        current_user: User,
        ws_in: WorkspaceUpdate,
    ) -> WorkspaceResponse:
        """Update workspace name (OWNER only)."""
        await self.check_workspace_access(workspace_id, current_user, required_role=WorkspaceMemberRole.OWNER)

        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(MSG_WORKSPACE_NOT_FOUND.format(id=workspace_id))

        update_data = ws_in.model_dump(exclude_unset=True)
        updated = await self.workspace_repo.update(workspace, **update_data)
        if self.cache:
            await self.cache.delete(f"workspaces:detail:{workspace_id}")
            await self.cache.delete_pattern("workspaces:user:*")
        return self._format_response(updated)

    async def delete_workspace(self, workspace_id: int, current_user: User) -> None:
        """Permanently delete workspace (OWNER only)."""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(MSG_WORKSPACE_NOT_FOUND.format(id=workspace_id))

        await self.check_workspace_access(workspace_id, current_user, required_role=WorkspaceMemberRole.OWNER)
        await self.workspace_repo.delete(workspace)
        if self.cache:
            await self.cache.delete(f"workspaces:detail:{workspace_id}")
            await self.cache.delete_pattern("workspaces:user:*")
            await self.cache.delete_pattern("projects:*")
            await self.cache.delete_pattern("tasks:*")

    async def add_member(
        self,
        workspace_id: int,
        current_user: User,
        member_in: WorkspaceMemberAdd,
        background_tasks: BackgroundTasks | None = None,
    ) -> WorkspaceMemberResponse:
        """Invite/add member to workspace (OWNER only)."""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(MSG_WORKSPACE_NOT_FOUND.format(id=workspace_id))

        await self.check_workspace_access(workspace_id, current_user, required_role=WorkspaceMemberRole.OWNER)

        target_user = None
        if member_in.user_id is not None:
            target_user = await self.user_repo.get_by_id(member_in.user_id)
        elif member_in.email is not None:
            target_user = await self.user_repo.get_by_email(member_in.email)

        if not target_user:
            identifier = member_in.user_id or member_in.email
            raise NotFoundException(MSG_USER_NOT_FOUND.format(id=identifier))

        if target_user.id == workspace.owner_id:
            raise BadRequestException(MSG_OWNER_ALREADY_MEMBER)

        existing = await self.workspace_repo.get_member(workspace_id, target_user.id)
        if existing:
            raise ConflictException(MSG_MEMBER_ALREADY_EXISTS)

        member = await self.workspace_repo.add_member(
            workspace_id=workspace_id,
            user_id=target_user.id,
            role=member_in.role,
        )
        if self.cache:
            await self.cache.delete(f"workspaces:detail:{workspace_id}")
            await self.cache.delete_pattern("workspaces:user:*")
            await self.cache.delete_pattern("tasks:*")
        if background_tasks:
            background_tasks.add_task(
                NotificationService.send_workspace_invitation,
                user_id=target_user.id,
                workspace_name=workspace.name,
                role=member.role.value,
            )
        return WorkspaceMemberResponse(
            user_id=target_user.id,
            email=target_user.email,
            full_name=target_user.full_name,
            role=member.role,
        )

    async def remove_member(
        self,
        workspace_id: int,
        current_user: User,
        target_user_id: int,
    ) -> None:
        """Remove member from workspace (OWNER only)."""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundException(MSG_WORKSPACE_NOT_FOUND.format(id=workspace_id))

        await self.check_workspace_access(workspace_id, current_user, required_role=WorkspaceMemberRole.OWNER)

        if target_user_id == workspace.owner_id:
            raise BadRequestException(MSG_CANNOT_REMOVE_OWNER)

        removed = await self.workspace_repo.remove_member(workspace_id, target_user_id)
        if not removed:
            raise NotFoundException(MSG_MEMBER_NOT_FOUND)
        if self.cache:
            await self.cache.delete(f"workspaces:detail:{workspace_id}")
            await self.cache.delete_pattern("workspaces:user:*")
            await self.cache.delete_pattern("tasks:*")
