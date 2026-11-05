import math

from fastapi import BackgroundTasks

from app.core.cache import cache_service
from app.core.constants import (
    DEFAULT_CACHE_TTL_SECONDS,
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MSG_LABEL_NOT_FOUND,
    MSG_LABEL_NOT_IN_PROJECT,
    MSG_PROJECT_NOT_FOUND,
    MSG_TASK_NOT_FOUND,
    MSG_USER_NOT_FOUND,
)
from app.core.exceptions import NotFoundException
from app.core.notifications import send_task_assignment_email
from app.models.enums import TaskPriority, TaskStatus, WorkspaceMemberRole
from app.models.task import Task
from app.models.user import User
from app.repositories.label_repository import LabelRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.label import LabelResponse
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from app.services.workspace_service import WorkspaceService


class TaskService:
    def __init__(
        self,
        task_repo: TaskRepository,
        project_repo: ProjectRepository,
        user_repo: UserRepository,
        label_repo: LabelRepository,
        workspace_service: WorkspaceService,
    ) -> None:
        self.task_repo = task_repo
        self.project_repo = project_repo
        self.user_repo = user_repo
        self.label_repo = label_repo
        self.workspace_service = workspace_service

    async def _invalidate_project_cache(self, project_id: int) -> None:
        """Invalidate all cached task lists for this project."""
        await cache_service.delete_pattern(f"tasks:project:{project_id}:*")

    def _format_task_response(self, task: Task) -> TaskResponse:
        labels_dto = [LabelResponse.model_validate(lbl) for lbl in task.labels]
        comments_count = len(task.comments) if task.comments else 0
        assignee_name = task.assignee.full_name if task.assignee else None

        return TaskResponse(
            id=task.id,
            project_id=task.project_id,
            assignee_id=task.assignee_id,
            assignee_name=assignee_name,
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            due_date=task.due_date,
            created_by=task.created_by,
            created_at=task.created_at,
            labels=labels_dto,
            comments_count=comments_count,
        )

    async def create_task(
        self,
        project_id: int,
        current_user: User,
        task_in: TaskCreate,
        background_tasks: BackgroundTasks | None = None,
    ) -> TaskResponse:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=project_id))

        await self.workspace_service.check_workspace_access(
            project.workspace_id, current_user, required_role=WorkspaceMemberRole.EDITOR
        )

        assignee_user = None
        if task_in.assignee_id:
            assignee_user = await self.user_repo.get_by_id(task_in.assignee_id)
            if not assignee_user:
                raise NotFoundException(MSG_USER_NOT_FOUND.format(id=task_in.assignee_id))

        created_task = await self.task_repo.create(project_id=project_id, created_by=current_user.id, task_in=task_in)

        await self._invalidate_project_cache(project_id)

        if assignee_user and background_tasks:
            background_tasks.add_task(
                send_task_assignment_email,
                to_email=assignee_user.email,
                assignee_name=assignee_user.full_name,
                task_id=created_task.id,
                task_title=created_task.title,
                project_name=project.name,
                assigned_by_name=current_user.full_name,
            )

        return self._format_task_response(created_task)

    async def list_tasks(
        self,
        project_id: int,
        current_user: User,
        status_filter: TaskStatus | None = None,
        priority_filter: TaskPriority | None = None,
        assignee_id: int | None = None,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> PaginatedResponse[TaskResponse]:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=project_id))

        await self.workspace_service.check_workspace_access(project.workspace_id, current_user)

        cache_key = (
            f"tasks:project:{project_id}:"
            f"st={status_filter}:pr={priority_filter}:asg={assignee_id}:"
            f"p={page}:s={page_size}"
        )
        cached_data = await cache_service.get_json(cache_key)
        if cached_data is not None:
            return PaginatedResponse[TaskResponse].model_validate(cached_data)

        skip = (page - 1) * page_size
        items, total = await self.task_repo.list_by_project(
            project_id=project_id,
            status=status_filter,
            priority=priority_filter,
            assignee_id=assignee_id,
            skip=skip,
            limit=page_size,
        )

        total_pages = math.ceil(total / page_size) if total > 0 else 0
        response = PaginatedResponse(
            items=[self._format_task_response(t) for t in items],
            meta=PaginationMeta(
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            ),
        )

        await cache_service.set_json(cache_key, response.model_dump(mode="json"), ttl=DEFAULT_CACHE_TTL_SECONDS)
        return response

    async def get_task(self, task_id: int, current_user: User) -> TaskResponse:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))
        project = await self.project_repo.get_by_id(task.project_id)
        if project:
            await self.workspace_service.check_workspace_access(project.workspace_id, current_user)
        return self._format_task_response(task)

    async def update_task(
        self,
        task_id: int,
        current_user: User,
        task_in: TaskUpdate,
        background_tasks: BackgroundTasks | None = None,
    ) -> TaskResponse:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))
        project = await self.project_repo.get_by_id(task.project_id)
        if project:
            await self.workspace_service.check_workspace_access(
                project.workspace_id, current_user, required_role=WorkspaceMemberRole.EDITOR
            )

        assignee_changed = False
        new_assignee_user = None
        if task_in.assignee_id is not None and task_in.assignee_id != task.assignee_id:
            new_assignee_user = await self.user_repo.get_by_id(task_in.assignee_id)
            if not new_assignee_user:
                raise NotFoundException(MSG_USER_NOT_FOUND.format(id=task_in.assignee_id))
            assignee_changed = True

        updated_task = await self.task_repo.update(task, task_in)
        await self._invalidate_project_cache(task.project_id)

        if assignee_changed and new_assignee_user and background_tasks and project:
            background_tasks.add_task(
                send_task_assignment_email,
                to_email=new_assignee_user.email,
                assignee_name=new_assignee_user.full_name,
                task_id=updated_task.id,
                task_title=updated_task.title,
                project_name=project.name,
                assigned_by_name=current_user.full_name,
            )

        return self._format_task_response(updated_task)

    async def delete_task(self, task_id: int, current_user: User) -> None:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))
        project = await self.project_repo.get_by_id(task.project_id)
        if project:
            await self.workspace_service.check_workspace_access(
                project.workspace_id, current_user, required_role=WorkspaceMemberRole.EDITOR
            )
        await self.task_repo.delete(task)
        await self._invalidate_project_cache(task.project_id)

    async def add_label_to_task(self, task_id: int, label_id: int, current_user: User) -> TaskResponse:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))
        project = await self.project_repo.get_by_id(task.project_id)
        if project:
            await self.workspace_service.check_workspace_access(
                project.workspace_id, current_user, required_role=WorkspaceMemberRole.EDITOR
            )
        label = await self.label_repo.get_by_id(label_id)
        if not label or label.project_id != task.project_id:
            raise NotFoundException(MSG_LABEL_NOT_IN_PROJECT.format(id=label_id))
        updated = await self.task_repo.add_label(task, label)
        await self._invalidate_project_cache(task.project_id)
        return self._format_task_response(updated)

    async def remove_label_from_task(self, task_id: int, label_id: int, current_user: User) -> TaskResponse:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))
        project = await self.project_repo.get_by_id(task.project_id)
        if project:
            await self.workspace_service.check_workspace_access(
                project.workspace_id, current_user, required_role=WorkspaceMemberRole.EDITOR
            )
        label = await self.label_repo.get_by_id(label_id)
        if not label:
            raise NotFoundException(MSG_LABEL_NOT_FOUND.format(id=label_id))
        updated = await self.task_repo.remove_label(task, label)
        await self._invalidate_project_cache(task.project_id)
        return self._format_task_response(updated)
