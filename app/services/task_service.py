import math

from app.core.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MSG_TASK_NOT_FOUND
from app.core.exceptions import NotFoundException
from app.models.enums import TaskPriority, TaskStatus
from app.models.task import Task
from app.repositories.task_repository import TaskRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate


class TaskService:
    """Business logic layer for Task operations, receiving TaskRepository via DI."""

    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def _to_response(self, task: Task) -> TaskResponse:
        return TaskResponse(
            id=task.id,
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            due_date=task.due_date,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    async def list_tasks(
        self,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        search: str | None = None,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> PaginatedResponse[TaskResponse]:
        skip = (page - 1) * page_size
        tasks, total = await self.repository.list_tasks(
            skip=skip,
            limit=page_size,
            status=status,
            priority=priority,
            search=search,
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

    async def get_task(self, task_id: int) -> TaskResponse:
        task = await self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))
        return self._to_response(task)

    async def create_task(self, task_in: TaskCreate) -> TaskResponse:
        task = await self.repository.create_task(
            title=task_in.title,
            description=task_in.description,
            status=task_in.status,
            priority=task_in.priority,
            due_date=task_in.due_date,
        )
        return self._to_response(task)

    async def update_task(self, task_id: int, task_in: TaskUpdate) -> TaskResponse:
        task = await self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))

        update_data = task_in.model_dump(exclude_unset=True)
        updated_task = await self.repository.update(task, **update_data)
        return self._to_response(updated_task)

    async def delete_task(self, task_id: int) -> None:
        task = await self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))
        await self.repository.delete(task)
