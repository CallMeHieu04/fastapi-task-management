import math

from app.core.constants import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MSG_PROJECT_NOT_FOUND,
    MSG_TASK_NOT_FOUND,
    MSG_USER_NOT_FOUND,
)
from app.core.exceptions import NotFoundException
from app.models.enums import TaskPriority, TaskStatus, WorkspaceMemberRole
from app.models.task import Task
from app.models.user import User
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from app.services.workspace_service import WorkspaceService


class TaskService:
    """Business logic layer for Task operations, receiving repositories and WorkspaceService via DI."""

    def __init__(
        self,
        repository: TaskRepository,
        project_repo: ProjectRepository | None = None,
        workspace_service: WorkspaceService | None = None,
        user_repo: UserRepository | None = None,
    ) -> None:
        self.repository = repository
        self.project_repo = project_repo
        self.workspace_service = workspace_service
        self.user_repo = user_repo

    def _to_response(self, task: Task) -> TaskResponse:
        return TaskResponse.model_validate(task)

    async def _verify_project_access(
        self,
        project_id: int,
        current_user: User | None,
        required_role: WorkspaceMemberRole | None = None,
    ) -> None:
        """Verify that the project exists and the user has required workspace permissions."""
        if self.project_repo is None or self.workspace_service is None:
            return

        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=project_id))

        if current_user:
            await self.workspace_service.check_workspace_access(
                workspace_id=project.workspace_id,
                current_user=current_user,
                required_role=required_role,
            )

    async def _verify_assignee(self, assignee_id: int | None) -> None:
        """Verify that assignee exists if provided."""
        if assignee_id is not None and self.user_repo is not None:
            user = await self.user_repo.get_by_id(assignee_id)
            if not user:
                raise NotFoundException(MSG_USER_NOT_FOUND.format(id=assignee_id))

    async def list_tasks(
        self,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        search: str | None = None,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
        project_id: int | None = None,
        current_user: User | None = None,
    ) -> PaginatedResponse[TaskResponse]:
        if project_id is not None and current_user is not None:
            await self._verify_project_access(project_id, current_user)

        skip = (page - 1) * page_size
        tasks, total = await self.repository.list_tasks(
            skip=skip,
            limit=page_size,
            status=status,
            priority=priority,
            search=search,
            project_id=project_id,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return PaginatedResponse(
            items=[self._to_response(t) for t in tasks],
            meta=PaginationMeta(
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            ),
        )

    async def get_task(self, task_id: int, current_user: User | None = None) -> TaskResponse:
        task = await self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))

        if task.project_id is not None and current_user is not None:
            await self._verify_project_access(task.project_id, current_user)

        return self._to_response(task)

    async def create_task(self, task_in: TaskCreate, current_user: User | None = None) -> TaskResponse:
        if task_in.project_id is not None:
            await self._verify_project_access(
                task_in.project_id,
                current_user,
                required_role=WorkspaceMemberRole.EDITOR,
            )

        await self._verify_assignee(task_in.assignee_id)

        created_by = current_user.id if current_user else None
        task = await self.repository.create_task(
            title=task_in.title,
            description=task_in.description,
            status=task_in.status,
            priority=task_in.priority,
            due_date=task_in.due_date,
            project_id=task_in.project_id,
            assignee_id=task_in.assignee_id,
            created_by=created_by,
        )
        return self._to_response(task)

    async def create_project_task(
        self,
        project_id: int,
        current_user: User,
        task_in: TaskCreate,
    ) -> TaskResponse:
        """Create a task directly attached to a specific project."""
        task_in.project_id = project_id
        return await self.create_task(task_in=task_in, current_user=current_user)

    async def list_project_tasks(
        self,
        project_id: int,
        current_user: User,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        search: str | None = None,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> PaginatedResponse[TaskResponse]:
        """List tasks belonging to a specific project."""
        return await self.list_tasks(
            status=status,
            priority=priority,
            search=search,
            page=page,
            page_size=page_size,
            project_id=project_id,
            current_user=current_user,
        )

    async def update_task(
        self,
        task_id: int,
        task_in: TaskUpdate,
        current_user: User | None = None,
    ) -> TaskResponse:
        task = await self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))

        if task.project_id is not None and current_user is not None:
            await self._verify_project_access(
                task.project_id,
                current_user,
                required_role=WorkspaceMemberRole.EDITOR,
            )

        if task_in.assignee_id is not None:
            await self._verify_assignee(task_in.assignee_id)

        update_data = task_in.model_dump(exclude_unset=True)
        updated_task = await self.repository.update(task, **update_data)
        return self._to_response(updated_task)

    async def delete_task(self, task_id: int, current_user: User | None = None) -> None:
        task = await self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))

        if task.project_id is not None and current_user is not None:
            await self._verify_project_access(
                task.project_id,
                current_user,
                required_role=WorkspaceMemberRole.EDITOR,
            )

        await self.repository.delete(task)
