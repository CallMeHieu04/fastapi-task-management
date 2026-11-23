from datetime import datetime

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskPriority, TaskStatus
from app.models.label import Label
from app.models.project import Project
from app.models.task import Task
from app.models.workspace import Workspace, WorkspaceMember
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
        assignee_id: int | None = None,
        label_id: int | None = None,
        due_date_from: datetime | None = None,
        due_date_to: datetime | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
        accessible_user_id: int | None = None,
    ) -> tuple[list[Task], int]:
        """Fetch tasks with filtering, search query, sorting, and pagination.

        If accessible_user_id is provided, restricts tasks to workspaces where the user is an owner/member.
        """
        query = select(Task)

        if project_id is not None:
            query = query.where(Task.project_id == project_id)
        elif accessible_user_id is not None:
            accessible_workspaces = (
                select(Workspace.id)
                .outerjoin(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
                .where(
                    or_(
                        Workspace.owner_id == accessible_user_id,
                        WorkspaceMember.user_id == accessible_user_id,
                    )
                )
            )
            accessible_projects = select(Project.id).where(Project.workspace_id.in_(accessible_workspaces))
            query = query.where(
                or_(
                    Task.project_id.in_(accessible_projects),
                    Task.created_by == accessible_user_id,
                )
            )

        if status:
            query = query.where(Task.status == status)
        if priority:
            query = query.where(Task.priority == priority)
        if assignee_id is not None:
            query = query.where(Task.assignee_id == assignee_id)
        if label_id is not None:
            query = query.where(Task.labels.any(Label.id == label_id))
        if due_date_from is not None:
            query = query.where(Task.due_date >= due_date_from)
        if due_date_to is not None:
            query = query.where(Task.due_date <= due_date_to)
        if search:
            pattern = f"%{search.lower()}%"
            query = query.where((func.lower(Task.title).like(pattern)) | (func.lower(Task.description).like(pattern)))

        # Count total matching rows
        count_stmt = select(func.count()).select_from(query.subquery())
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        # Dynamic sorting with tie-breaker
        sort_by_str = sort_by.value if hasattr(sort_by, "value") else str(sort_by)
        order_str = order.value if hasattr(order, "value") else str(order)

        if sort_by_str == "priority":
            priority_order = case(
                (Task.priority == TaskPriority.LOW, 1),
                (Task.priority == TaskPriority.MEDIUM, 2),
                (Task.priority == TaskPriority.HIGH, 3),
                (Task.priority == TaskPriority.URGENT, 4),
                else_=0,
            )
            sort_expr = priority_order.asc() if order_str.lower() == "asc" else priority_order.desc()
        else:
            sort_column_map = {
                "created_at": Task.created_at,
                "due_date": Task.due_date,
                "title": Task.title,
                "status": Task.status,
                "updated_at": Task.updated_at,
            }
            col = sort_column_map.get(sort_by_str, Task.created_at)
            sort_expr = col.asc() if order_str.lower() == "asc" else col.desc()

        # Fetch paginated slice ordered stably by sort expression and primary key
        stmt = query.order_by(sort_expr, Task.id.desc()).offset(skip).limit(limit)
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
        created_by: int | None = None,
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
            created_by=created_by,
        )
