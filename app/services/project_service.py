from app.core.constants import MSG_PROJECT_NOT_FOUND
from app.core.exceptions import NotFoundException
from app.models.enums import ProjectStatus, WorkspaceMemberRole
from app.models.user import User
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.workspace_service import WorkspaceService


class ProjectService:
    def __init__(
        self,
        project_repo: ProjectRepository,
        workspace_service: WorkspaceService,
    ) -> None:
        self.project_repo = project_repo
        self.workspace_service = workspace_service

    async def create_project(self, workspace_id: int, current_user: User, project_in: ProjectCreate) -> ProjectResponse:
        await self.workspace_service.check_workspace_access(
            workspace_id, current_user, required_role=WorkspaceMemberRole.EDITOR
        )
        project = await self.project_repo.create(workspace_id=workspace_id, project_in=project_in)
        return ProjectResponse.model_validate(project)

    async def list_projects(self, workspace_id: int, current_user: User) -> list[ProjectResponse]:
        await self.workspace_service.check_workspace_access(workspace_id, current_user)
        projects = await self.project_repo.list_by_workspace(workspace_id)
        return [ProjectResponse.model_validate(p) for p in projects]

    async def get_project(self, project_id: int, current_user: User) -> ProjectResponse:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=project_id))
        await self.workspace_service.check_workspace_access(project.workspace_id, current_user)
        return ProjectResponse.model_validate(project)

    async def update_project(self, project_id: int, current_user: User, project_in: ProjectUpdate) -> ProjectResponse:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=project_id))
        await self.workspace_service.check_workspace_access(
            project.workspace_id, current_user, required_role=WorkspaceMemberRole.EDITOR
        )
        updated = await self.project_repo.update(project, project_in)
        return ProjectResponse.model_validate(updated)

    async def archive_project(self, project_id: int, current_user: User) -> ProjectResponse:
        return await self.update_project(
            project_id=project_id,
            current_user=current_user,
            project_in=ProjectUpdate(status=ProjectStatus.ARCHIVED),
        )

    async def delete_project(self, project_id: int, current_user: User) -> None:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=project_id))
        await self.workspace_service.check_workspace_access(
            project.workspace_id, current_user, required_role=WorkspaceMemberRole.OWNER
        )
        await self.project_repo.delete(project)
