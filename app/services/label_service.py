from app.core.constants import MSG_PROJECT_NOT_FOUND
from app.core.exceptions import NotFoundException
from app.models.enums import WorkspaceMemberRole
from app.models.user import User
from app.repositories.label_repository import LabelRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.label import LabelCreate, LabelResponse
from app.services.workspace_service import WorkspaceService


class LabelService:
    def __init__(
        self,
        label_repo: LabelRepository,
        project_repo: ProjectRepository,
        workspace_service: WorkspaceService,
    ) -> None:
        self.label_repo = label_repo
        self.project_repo = project_repo
        self.workspace_service = workspace_service

    async def create_label(self, project_id: int, current_user: User, label_in: LabelCreate) -> LabelResponse:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=project_id))
        await self.workspace_service.check_workspace_access(
            project.workspace_id, current_user, required_role=WorkspaceMemberRole.EDITOR
        )
        label = await self.label_repo.create(project_id=project_id, label_in=label_in)
        return LabelResponse.model_validate(label)

    async def list_labels(self, project_id: int, current_user: User) -> list[LabelResponse]:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=project_id))
        await self.workspace_service.check_workspace_access(project.workspace_id, current_user)
        labels = await self.label_repo.list_by_project(project_id)
        return [LabelResponse.model_validate(lbl) for lbl in labels]
