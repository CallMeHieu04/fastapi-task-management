from app.core.constants import (
    MSG_LABEL_NOT_FOUND,
    MSG_LABEL_NOT_IN_PROJECT,
    MSG_PROJECT_NOT_FOUND,
    MSG_TASK_NOT_FOUND,
)
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.enums import WorkspaceMemberRole
from app.models.user import User
from app.repositories.label_repository import LabelRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.label import LabelCreate, LabelResponse, LabelUpdate
from app.schemas.task import TaskResponse
from app.services.workspace_service import WorkspaceService


class LabelService:
    """Service handling Label lifecycle and attachment to Tasks with workspace RBAC."""

    def __init__(
        self,
        label_repo: LabelRepository,
        project_repo: ProjectRepository,
        task_repo: TaskRepository,
        workspace_service: WorkspaceService,
    ) -> None:
        self.label_repo = label_repo
        self.project_repo = project_repo
        self.task_repo = task_repo
        self.workspace_service = workspace_service

    async def create_label(
        self,
        project_id: int,
        current_user: User,
        label_in: LabelCreate,
    ) -> LabelResponse:
        """Create a label in a project (OWNER or EDITOR only)."""
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=project_id))

        await self.workspace_service.check_workspace_access(
            workspace_id=project.workspace_id,
            current_user=current_user,
            required_role=WorkspaceMemberRole.EDITOR,
        )

        label = await self.label_repo.create(
            project_id=project_id,
            name=label_in.name,
            color=label_in.color,
        )
        return LabelResponse.model_validate(label)

    async def list_labels(
        self,
        project_id: int,
        current_user: User,
    ) -> list[LabelResponse]:
        """List all labels in a project (Workspace members only)."""
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=project_id))

        await self.workspace_service.check_workspace_access(
            workspace_id=project.workspace_id,
            current_user=current_user,
        )

        labels = await self.label_repo.list_by_project(project_id=project_id)
        return [LabelResponse.model_validate(lbl) for lbl in labels]

    async def update_label(
        self,
        label_id: int,
        current_user: User,
        label_in: LabelUpdate,
    ) -> LabelResponse:
        """Update label attributes (OWNER or EDITOR only)."""
        label = await self.label_repo.get_by_id(label_id)
        if not label:
            raise NotFoundException(MSG_LABEL_NOT_FOUND.format(id=label_id))

        project = await self.project_repo.get_by_id(label.project_id)
        if not project:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=label.project_id))

        await self.workspace_service.check_workspace_access(
            workspace_id=project.workspace_id,
            current_user=current_user,
            required_role=WorkspaceMemberRole.EDITOR,
        )

        update_data = label_in.model_dump(exclude_unset=True)
        updated = await self.label_repo.update(label, **update_data)
        return LabelResponse.model_validate(updated)

    async def delete_label(
        self,
        label_id: int,
        current_user: User,
    ) -> None:
        """Delete a label (OWNER or EDITOR only)."""
        label = await self.label_repo.get_by_id(label_id)
        if not label:
            raise NotFoundException(MSG_LABEL_NOT_FOUND.format(id=label_id))

        project = await self.project_repo.get_by_id(label.project_id)
        if not project:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=label.project_id))

        await self.workspace_service.check_workspace_access(
            workspace_id=project.workspace_id,
            current_user=current_user,
            required_role=WorkspaceMemberRole.EDITOR,
        )
        await self.label_repo.delete(label)

    async def attach_label_to_task(
        self,
        task_id: int,
        label_id: int,
        current_user: User,
    ) -> TaskResponse:
        """Attach a project label to a task (OWNER or EDITOR only)."""
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))

        if task.project_id is None:
            raise BadRequestException("Cannot attach label to a task without a project.")

        project = await self.project_repo.get_by_id(task.project_id)
        if not project:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=task.project_id))

        await self.workspace_service.check_workspace_access(
            workspace_id=project.workspace_id,
            current_user=current_user,
            required_role=WorkspaceMemberRole.EDITOR,
        )

        label = await self.label_repo.get_by_id(label_id)
        if not label:
            raise NotFoundException(MSG_LABEL_NOT_FOUND.format(id=label_id))

        if label.project_id != task.project_id:
            raise BadRequestException(MSG_LABEL_NOT_IN_PROJECT.format(id=label_id))

        updated_task = await self.label_repo.attach_label_to_task(task=task, label=label)
        return TaskResponse.model_validate(updated_task)

    async def detach_label_from_task(
        self,
        task_id: int,
        label_id: int,
        current_user: User,
    ) -> TaskResponse:
        """Detach a label from a task (OWNER or EDITOR only)."""
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))

        if task.project_id is None:
            raise BadRequestException("Cannot detach label from a task without a project.")

        project = await self.project_repo.get_by_id(task.project_id)
        if not project:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=task.project_id))

        await self.workspace_service.check_workspace_access(
            workspace_id=project.workspace_id,
            current_user=current_user,
            required_role=WorkspaceMemberRole.EDITOR,
        )

        label = await self.label_repo.get_by_id(label_id)
        if not label:
            raise NotFoundException(MSG_LABEL_NOT_FOUND.format(id=label_id))

        updated_task = await self.label_repo.detach_label_from_task(task=task, label=label)
        return TaskResponse.model_validate(updated_task)
