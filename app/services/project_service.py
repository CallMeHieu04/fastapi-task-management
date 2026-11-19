import math

from app.core.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MSG_PROJECT_NOT_FOUND
from app.core.exceptions import NotFoundException
from app.models.enums import ProjectStatus, WorkspaceMemberRole
from app.models.project import Project
from app.models.user import User
from app.repositories.project_repository import ProjectRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.workspace_service import WorkspaceService


class ProjectService:
    """Service handling Project lifecycle and role-based access control within Workspaces."""

    def __init__(
        self,
        project_repo: ProjectRepository,
        workspace_service: WorkspaceService,
    ) -> None:
        self.project_repo = project_repo
        self.workspace_service = workspace_service

    async def get_project_with_access(
        self,
        project_id: int,
        current_user: User,
        required_role: WorkspaceMemberRole | None = None,
    ) -> Project:
        """Fetch project ensuring current user has access, returning 404 for non-members to prevent ID probing."""
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=project_id))

        try:
            await self.workspace_service.check_workspace_access(
                workspace_id=project.workspace_id,
                current_user=current_user,
                required_role=required_role,
            )
        except NotFoundException:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=project_id)) from None

        return project

    async def create_project(
        self,
        workspace_id: int,
        current_user: User,
        project_in: ProjectCreate,
    ) -> ProjectResponse:
        """Create a new project in the workspace (OWNER or EDITOR only)."""
        await self.workspace_service.check_workspace_access(
            workspace_id=workspace_id,
            current_user=current_user,
            required_role=WorkspaceMemberRole.EDITOR,
        )
        project = await self.project_repo.create(
            workspace_id=workspace_id,
            name=project_in.name,
            description=project_in.description,
            status=ProjectStatus.ACTIVE,
        )
        return ProjectResponse.model_validate(project)

    async def list_projects(
        self,
        workspace_id: int,
        current_user: User,
        page: int = DEFAULT_PAGE,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> PaginatedResponse[ProjectResponse]:
        """List paginated projects in the workspace (Workspace members only)."""
        await self.workspace_service.check_workspace_access(
            workspace_id=workspace_id,
            current_user=current_user,
        )
        projects, total = await self.project_repo.list_by_workspace(
            workspace_id=workspace_id,
            page=page,
            limit=limit,
        )
        total_pages = math.ceil(total / limit) if total > 0 else 0
        return PaginatedResponse(
            items=[ProjectResponse.model_validate(p) for p in projects],
            meta=PaginationMeta(
                total=total,
                page=page,
                page_size=limit,
                total_pages=total_pages,
            ),
        )

    async def get_project(
        self,
        project_id: int,
        current_user: User,
    ) -> ProjectResponse:
        """Get project details (Workspace members only)."""
        project = await self.get_project_with_access(project_id=project_id, current_user=current_user)
        return ProjectResponse.model_validate(project)

    async def update_project(
        self,
        project_id: int,
        current_user: User,
        project_in: ProjectUpdate,
    ) -> ProjectResponse:
        """Update project details (OWNER or EDITOR only)."""
        project = await self.get_project_with_access(
            project_id=project_id,
            current_user=current_user,
            required_role=WorkspaceMemberRole.EDITOR,
        )

        update_data = project_in.model_dump(exclude_unset=True)
        updated = await self.project_repo.update(project, **update_data)
        return ProjectResponse.model_validate(updated)

    async def delete_project(
        self,
        project_id: int,
        current_user: User,
    ) -> None:
        """Delete project and all associated tasks (OWNER or EDITOR only)."""
        project = await self.get_project_with_access(
            project_id=project_id,
            current_user=current_user,
            required_role=WorkspaceMemberRole.EDITOR,
        )
        await self.project_repo.delete(project)
