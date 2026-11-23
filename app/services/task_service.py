import math
from typing import TYPE_CHECKING

from app.core.cache import CacheService
from app.core.constants import (
    MSG_ASSIGNEE_NOT_MEMBER,
    MSG_PROJECT_ARCHIVED,
    MSG_PROJECT_NOT_FOUND,
    MSG_TASK_NOT_FOUND,
    MSG_USER_NOT_FOUND,
)
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.enums import ProjectStatus, TaskStatus, UserRole, WorkspaceMemberRole
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.task import ProjectTaskCreate, TaskCreate, TaskResponse, TaskUpdate
from app.services.workspace_service import WorkspaceService

if TYPE_CHECKING:
    from app.api.deps import TaskFilterParams


class TaskService:
    """Business logic layer for Task operations, receiving repositories, WorkspaceService, and CacheService via DI."""

    def __init__(
        self,
        repository: TaskRepository,
        project_repo: ProjectRepository,
        workspace_service: WorkspaceService,
        user_repo: UserRepository,
        cache_service: CacheService | None = None,
    ) -> None:
        self.repository = repository
        self.project_repo = project_repo
        self.workspace_service = workspace_service
        self.user_repo = user_repo
        self.cache = cache_service

    def _to_response(self, task: Task) -> TaskResponse:
        return TaskResponse.model_validate(task)

    async def _get_project_with_access(
        self,
        project_id: int,
        current_user: User,
        required_role: WorkspaceMemberRole | None = None,
        for_write: bool = False,
    ) -> Project:
        """Fetch project and verify access. Returns 404 for non-members and 400 if project is archived on writes."""
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

        if for_write and project.status == ProjectStatus.ARCHIVED:
            raise BadRequestException(MSG_PROJECT_ARCHIVED)

        return project

    async def _verify_assignee(self, workspace_id: int | None, assignee_id: int | None) -> None:
        """Verify that assignee exists and belongs to the project's workspace."""
        if assignee_id is None:
            return

        user = await self.user_repo.get_by_id(assignee_id)
        if not user:
            raise NotFoundException(MSG_USER_NOT_FOUND.format(id=assignee_id))

        if workspace_id is not None:
            member = await self.workspace_service.workspace_repo.get_member(workspace_id, assignee_id)
            if not member:
                raise BadRequestException(MSG_ASSIGNEE_NOT_MEMBER)

    async def list_tasks(
        self,
        filters: "TaskFilterParams",
        current_user: User,
    ) -> PaginatedResponse[TaskResponse]:
        """Fetch paginated tasks with filtering, search, sorting, and caching.

        Out-of-workspace projects return 404; global list filters to user's workspaces.
        """
        if filters.project_id is not None:
            await self._get_project_with_access(filters.project_id, current_user)
            accessible_user_id = None
        else:
            accessible_user_id = current_user.id if current_user.role != UserRole.ADMIN else None

        filter_items = [
            f"{k}={v.value if hasattr(v, 'value') else (v.isoformat() if hasattr(v, 'isoformat') else v)}"
            for k, v in sorted(filters.__dict__.items())
        ]
        cache_key = f"tasks:list:u{current_user.id}:{':'.join(filter_items)}"
        if self.cache:
            cached = await self.cache.get_json(cache_key)
            if cached:
                return PaginatedResponse[TaskResponse].model_validate(cached)

        skip = (filters.page - 1) * filters.limit
        tasks, total = await self.repository.list_tasks(
            skip=skip,
            limit=filters.limit,
            status=filters.status,
            priority=filters.priority,
            search=filters.search,
            project_id=filters.project_id,
            assignee_id=filters.assignee_id,
            label_id=filters.label_id,
            due_date_from=filters.due_date_from,
            due_date_to=filters.due_date_to,
            sort_by=filters.sort_by,
            order=filters.order,
            accessible_user_id=accessible_user_id,
        )
        total_pages = math.ceil(total / filters.limit) if total > 0 else 0

        response = PaginatedResponse(
            items=[self._to_response(t) for t in tasks],
            meta=PaginationMeta(
                total=total,
                page=filters.page,
                page_size=filters.limit,
                total_pages=total_pages,
            ),
        )
        if self.cache:
            await self.cache.set_json(cache_key, response.model_dump())
        return response

    async def get_task(self, task_id: int, current_user: User) -> TaskResponse:
        """Get task by ID (verifying project/workspace access with caching)."""
        cache_key = f"tasks:detail:{task_id}"
        if self.cache:
            cached = await self.cache.get_json(cache_key)
            if cached:
                if cached.get("project_id") is not None:
                    await self._get_project_with_access(cached["project_id"], current_user)
                return TaskResponse.model_validate(cached)

        task = await self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))

        if task.project_id is not None:
            await self._get_project_with_access(task.project_id, current_user)

        res = self._to_response(task)
        if self.cache:
            await self.cache.set_json(cache_key, res.model_dump())
        return res

    async def create_task(self, task_in: TaskCreate, current_user: User) -> TaskResponse:
        """Create a new task with validated project membership and assignee."""
        workspace_id = None
        if task_in.project_id is not None:
            project = await self._get_project_with_access(
                task_in.project_id,
                current_user,
                required_role=WorkspaceMemberRole.EDITOR,
                for_write=True,
            )
            workspace_id = project.workspace_id

        await self._verify_assignee(workspace_id, task_in.assignee_id)

        task = await self.repository.create_task(
            title=task_in.title,
            description=task_in.description,
            status=TaskStatus.TODO,
            priority=task_in.priority,
            due_date=task_in.due_date,
            project_id=task_in.project_id,
            assignee_id=task_in.assignee_id,
            created_by=current_user.id,
        )
        if self.cache:
            await self.cache.delete_pattern("tasks:u*")
            if task_in.project_id:
                await self.cache.delete_pattern(f"tasks:*pid{task_in.project_id}:*")
        return self._to_response(task)

    async def create_project_task(
        self,
        project_id: int,
        current_user: User,
        task_in: ProjectTaskCreate,
    ) -> TaskResponse:
        """Create a task directly attached to a specific project without mutating input."""
        project = await self._get_project_with_access(
            project_id,
            current_user,
            required_role=WorkspaceMemberRole.EDITOR,
            for_write=True,
        )
        await self._verify_assignee(project.workspace_id, task_in.assignee_id)

        task = await self.repository.create_task(
            title=task_in.title,
            description=task_in.description,
            status=TaskStatus.TODO,
            priority=task_in.priority,
            due_date=task_in.due_date,
            project_id=project_id,
            assignee_id=task_in.assignee_id,
            created_by=current_user.id,
        )
        if self.cache:
            await self.cache.delete_pattern("tasks:u*")
            await self.cache.delete_pattern(f"tasks:*pid{project_id}:*")
        return self._to_response(task)

    async def list_project_tasks(
        self,
        project_id: int,
        filters: "TaskFilterParams",
        current_user: User,
    ) -> PaginatedResponse[TaskResponse]:
        """List tasks belonging to a specific project."""
        filters.project_id = project_id
        return await self.list_tasks(filters=filters, current_user=current_user)

    async def update_task(
        self,
        task_id: int,
        task_in: TaskUpdate,
        current_user: User,
    ) -> TaskResponse:
        """Update task attributes with RBAC and assignee validation."""
        task = await self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))

        workspace_id = None
        if task.project_id is not None:
            project = await self._get_project_with_access(
                task.project_id,
                current_user,
                required_role=WorkspaceMemberRole.EDITOR,
                for_write=True,
            )
            workspace_id = project.workspace_id

        if task_in.assignee_id is not None:
            await self._verify_assignee(workspace_id, task_in.assignee_id)

        update_data = task_in.model_dump(exclude_unset=True)
        updated_task = await self.repository.update(task, **update_data)
        if self.cache:
            await self.cache.delete(f"tasks:detail:{task_id}")
            await self.cache.delete_pattern("tasks:u*")
            if task.project_id:
                await self.cache.delete_pattern(f"tasks:*pid{task.project_id}:*")
        return self._to_response(updated_task)

    async def delete_task(self, task_id: int, current_user: User) -> None:
        """Delete task (verifying EDITOR permission on project)."""
        task = await self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))

        if task.project_id is not None:
            await self._get_project_with_access(
                task.project_id,
                current_user,
                required_role=WorkspaceMemberRole.EDITOR,
                for_write=True,
            )

        project_id = task.project_id
        await self.repository.delete(task)
        if self.cache:
            await self.cache.delete(f"tasks:detail:{task_id}")
            await self.cache.delete_pattern("tasks:u*")
            if project_id:
                await self.cache.delete_pattern(f"tasks:*pid{project_id}:*")
