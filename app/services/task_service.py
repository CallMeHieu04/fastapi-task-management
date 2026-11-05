import math

from app.core.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MSG_TASK_NOT_FOUND
from app.core.exceptions import NotFoundException
from app.models.task import TaskModel, TaskPriority, TaskStatus
from app.repositories.task_repository import TaskRepository
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate


class TaskService:
    """Business logic layer for Task management.

    Receives TaskRepository via dependency injection, mapping internal TaskModel to TaskResponse.
    """

    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def _to_response(self, model: TaskModel) -> TaskResponse:
        return TaskResponse(
            id=model.id,
            title=model.title,
            description=model.description,
            status=model.status,
            priority=model.priority,
            due_date=model.due_date,
            created_at=model.created_at,
            updated_at=model.updated_at,
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
        models, total = await self.repository.get_all(
            skip=skip,
            limit=page_size,
            status=status,
            priority=priority,
            search=search,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return PaginatedResponse(
            items=[self._to_response(m) for m in models],
            meta=PaginationMeta(
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            ),
        )

    async def get_task(self, task_id: int) -> TaskResponse:
        model = await self.repository.get_by_id(task_id)
        if not model:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))
        return self._to_response(model)

    async def create_task(self, task_in: TaskCreate) -> TaskResponse:
        model = await self.repository.create(
            title=task_in.title,
            description=task_in.description,
            status=task_in.status,
            priority=task_in.priority,
            due_date=task_in.due_date,
        )
        return self._to_response(model)

    async def update_task(self, task_id: int, task_in: TaskUpdate) -> TaskResponse:
        update_data = task_in.model_dump(exclude_unset=True)
        model = await self.repository.update(task_id, update_data)
        if not model:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))
        return self._to_response(model)

    async def delete_task(self, task_id: int) -> None:
        deleted = await self.repository.delete(task_id)
        if not deleted:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))
