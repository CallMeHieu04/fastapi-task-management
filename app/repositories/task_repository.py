from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskPriority, TaskStatus
from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Specialized repository for Task entity inheriting BaseRepository[Task]."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Task, session)

    async def list_tasks(
        self,
        skip: int = 0,
        limit: int = 20,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        search: str | None = None,
        project_id: int | None = None,
    ) -> tuple[list[Task], int]:
        """Fetch tasks with filtering, search query, and pagination."""
        query = select(Task)

        if project_id is not None:
            query = query.where(Task.project_id == project_id)
        if status:
            query = query.where(Task.status == status)
        if priority:
            query = query.where(Task.priority == priority)
        if search:
            pattern = f"%{search.lower()}%"
            query = query.where((func.lower(Task.title).like(pattern)) | (func.lower(Task.description).like(pattern)))

        # Count total matching rows
        count_stmt = select(func.count()).select_from(query.subquery())
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        # Fetch paginated slice ordered by creation time
        stmt = query.order_by(Task.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def create_task(
        self,
        title: str,
        description: str | None = None,
        status: TaskStatus = TaskStatus.TODO,
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_date: datetime | None = None,
        project_id: int | None = None,
        assignee_id: int | None = None,
    ) -> Task:
        """Create and persist a new task record."""
        return await self.create(
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_date=due_date,
            project_id=project_id,
            assignee_id=assignee_id,
        )
