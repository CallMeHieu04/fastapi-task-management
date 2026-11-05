import math

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_service
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
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.task_repo = TaskRepository(session)
        self.project_repo = ProjectRepository(session)
        self.user_repo = UserRepository(session)
        self.label_repo = LabelRepository(session)
        self.workspace_service = WorkspaceService(session)

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project #{project_id} not found.",
            )

        # Check EDITOR access in the project's workspace
        await self.workspace_service._check_workspace_access(
            project.workspace_id, current_user, required_role=WorkspaceMemberRole.EDITOR
        )

        # If assignee_id specified, check that user exists and is member
        assignee_user = None
        if task_in.assignee_id:
            assignee_user = await self.user_repo.get_by_id(task_in.assignee_id)
            if not assignee_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assignee user #{task_in.assignee_id} not found.",
                )

        created_task = await self.task_repo.create(
            project_id=project_id, created_by=current_user.id, task_in=task_in
        )

        # Invalidate task cache for project
        await self._invalidate_project_cache(project_id)

        # Send background email notification if assignee is present
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
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[TaskResponse]:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project #{project_id} not found.",
            )

        await self.workspace_service._check_workspace_access(project.workspace_id, current_user)

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

        # Cache response for fast subsequent queries (mode="json" serializes datetimes to ISO strings)
        await cache_service.set_json(cache_key, response.model_dump(mode="json"), ttl=120)
        return response

    async def get_task(self, task_id: int, current_user: User) -> TaskResponse:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task #{task_id} not found.",
            )
        project = await self.project_repo.get_by_id(task.project_id)
        if project:
            await self.workspace_service._check_workspace_access(project.workspace_id, current_user)
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task #{task_id} not found.",
            )
        project = await self.project_repo.get_by_id(task.project_id)
        if project:
            await self.workspace_service._check_workspace_access(
                project.workspace_id, current_user, required_role=WorkspaceMemberRole.EDITOR
            )

        # Check assignee change for background notification
        assignee_changed = False
        new_assignee_user = None
        if task_in.assignee_id is not None and task_in.assignee_id != task.assignee_id:
            new_assignee_user = await self.user_repo.get_by_id(task_in.assignee_id)
            if not new_assignee_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assignee #{task_in.assignee_id} not found.",
                )
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task #{task_id} not found.",
            )
        project = await self.project_repo.get_by_id(task.project_id)
        if project:
            await self.workspace_service._check_workspace_access(
                project.workspace_id, current_user, required_role=WorkspaceMemberRole.EDITOR
            )
        await self.task_repo.delete(task)
        await self._invalidate_project_cache(task.project_id)

    async def add_label_to_task(
        self, task_id: int, label_id: int, current_user: User
    ) -> TaskResponse:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task #{task_id} not found.",
            )
        project = await self.project_repo.get_by_id(task.project_id)
        if project:
            await self.workspace_service._check_workspace_access(
                project.workspace_id, current_user, required_role=WorkspaceMemberRole.EDITOR
            )
        label = await self.label_repo.get_by_id(label_id)
        if not label or label.project_id != task.project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Label #{label_id} not found in this project.",
            )
        updated = await self.task_repo.add_label(task, label)
        await self._invalidate_project_cache(task.project_id)
        return self._format_task_response(updated)

    async def remove_label_from_task(
        self, task_id: int, label_id: int, current_user: User
    ) -> TaskResponse:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task #{task_id} not found.",
            )
        project = await self.project_repo.get_by_id(task.project_id)
        if project:
            await self.workspace_service._check_workspace_access(
                project.workspace_id, current_user, required_role=WorkspaceMemberRole.EDITOR
            )
        label = await self.label_repo.get_by_id(label_id)
        if not label:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Label #{label_id} not found.",
            )
        updated = await self.task_repo.remove_label(task, label)
        await self._invalidate_project_cache(task.project_id)
        return self._format_task_response(updated)
