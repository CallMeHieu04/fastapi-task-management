from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import TaskPriority, TaskStatus
from app.models.label import Label
from app.models.task import Task, task_labels
from app.schemas.task import TaskCreate, TaskUpdate


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, task_id: int) -> Task | None:
        stmt = (
            select(Task)
            .where(Task.id == task_id)
            .options(
                selectinload(Task.labels),
                selectinload(Task.comments),
                selectinload(Task.assignee),
                selectinload(Task.creator),
                selectinload(Task.project),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_project(
        self,
        project_id: int,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: int | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Task], int]:
        query = select(Task).where(Task.project_id == project_id)

        if status:
            query = query.where(Task.status == status)
        if priority:
            query = query.where(Task.priority == priority)
        if assignee_id is not None:
            query = query.where(Task.assignee_id == assignee_id)

        count_query = select(func.count()).select_from(query.subquery())
        total_res = await self.session.execute(count_query)
        total = total_res.scalar_one()

        stmt = (
            query.options(
                selectinload(Task.labels),
                selectinload(Task.comments),
                selectinload(Task.assignee),
            )
            .order_by(Task.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def create(self, project_id: int, created_by: int, task_in: TaskCreate) -> Task:
        task = Task(
            project_id=project_id,
            created_by=created_by,
            title=task_in.title,
            description=task_in.description,
            status=task_in.status,
            priority=task_in.priority,
            due_date=task_in.due_date,
            assignee_id=task_in.assignee_id,
        )
        self.session.add(task)
        await self.session.flush()

        # Handle initial labels directly via table insert to avoid implicit lazy load
        if task_in.label_ids:
            for lid in task_in.label_ids:
                stmt = select(Label).where(Label.id == lid, Label.project_id == project_id)
                res = await self.session.execute(stmt)
                lbl = res.scalars().first()
                if lbl:
                    ins_stmt = insert(task_labels).values(task_id=task.id, label_id=lbl.id)
                    await self.session.execute(ins_stmt)

        await self.session.commit()
        return await self.get_by_id(task.id)  # type: ignore

    async def update(self, task: Task, task_in: TaskUpdate) -> Task:
        update_data = task_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(task, field, value)
        await self.session.commit()
        return await self.get_by_id(task.id)  # type: ignore

    async def delete(self, task: Task) -> None:
        await self.session.delete(task)
        await self.session.commit()

    async def add_label(self, task: Task, label: Label) -> Task:
        # Check if already present
        check_stmt = select(task_labels).where(
            task_labels.c.task_id == task.id,
            task_labels.c.label_id == label.id,
        )
        existing = (await self.session.execute(check_stmt)).first()
        if not existing:
            ins_stmt = insert(task_labels).values(task_id=task.id, label_id=label.id)
            await self.session.execute(ins_stmt)
            await self.session.commit()
        return await self.get_by_id(task.id)  # type: ignore

    async def remove_label(self, task: Task, label: Label) -> Task:
        del_stmt = delete(task_labels).where(
            task_labels.c.task_id == task.id,
            task_labels.c.label_id == label.id,
        )
        await self.session.execute(del_stmt)
        await self.session.commit()
        return await self.get_by_id(task.id)  # type: ignore
