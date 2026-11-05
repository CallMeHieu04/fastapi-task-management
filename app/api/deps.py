from typing import Annotated

from fastapi import Depends, Query

from app.core.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.models.task import TaskPriority, TaskStatus
from app.repositories.task_repository import TaskRepository
from app.services.task_service import TaskService

# Singleton repository instance holding in-memory data for local runtime
_task_repository = TaskRepository()


def get_task_repository() -> TaskRepository:
    """Dependency provider for TaskRepository."""
    return _task_repository


def get_task_service(
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskService:
    """Dependency provider injecting TaskRepository into TaskService."""
    return TaskService(repository=repository)


class TaskFilterParams:
    """Query parameter dependency for task listing with filtering and pagination."""

    def __init__(
        self,
        status: Annotated[TaskStatus | None, Query(description="Filter by task status")] = None,
        priority: Annotated[TaskPriority | None, Query(description="Filter by priority")] = None,
        search: Annotated[str | None, Query(max_length=50, description="Keyword search in title/desc")] = None,
        page: Annotated[int, Query(ge=1, description="Page number starting at 1")] = DEFAULT_PAGE,
        limit: Annotated[
            int, Query(ge=1, le=MAX_PAGE_SIZE, description=f"Items per page (max {MAX_PAGE_SIZE})")
        ] = DEFAULT_PAGE_SIZE,
    ):
        self.status = status
        self.priority = priority
        self.search = search
        self.page = page
        self.limit = limit
