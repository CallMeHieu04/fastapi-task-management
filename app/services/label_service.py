
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WorkspaceMemberRole
from app.models.user import User
from app.repositories.label_repository import LabelRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.label import LabelCreate, LabelResponse
from app.services.workspace_service import WorkspaceService


class LabelService:
    def __init__(self, session: AsyncSession) -> None:
        self.label_repo = LabelRepository(session)
        self.project_repo = ProjectRepository(session)
        self.workspace_service = WorkspaceService(session)

    async def create_label(
        self, project_id: int, current_user: User, label_in: LabelCreate
    ) -> LabelResponse:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project #{project_id} not found.",
            )
        await self.workspace_service._check_workspace_access(
            project.workspace_id, current_user, required_role=WorkspaceMemberRole.EDITOR
        )
        label = await self.label_repo.create(project_id=project_id, label_in=label_in)
        return LabelResponse.model_validate(label)

    async def list_labels(self, project_id: int, current_user: User) -> list[LabelResponse]:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project #{project_id} not found.",
            )
        await self.workspace_service._check_workspace_access(project.workspace_id, current_user)
        labels = await self.label_repo.list_by_project(project_id)
        return [LabelResponse.model_validate(lbl) for lbl in labels]
