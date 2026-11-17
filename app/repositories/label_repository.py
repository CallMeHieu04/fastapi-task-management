from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.label import Label
from app.models.task import Task
from app.repositories.base import BaseRepository


class LabelRepository(BaseRepository[Label]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Label, session)

    async def list_by_project(self, project_id: int) -> list[Label]:
        stmt = select(Label).where(Label.project_id == project_id).order_by(Label.name.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def attach_label_to_task(self, task: Task, label: Label) -> Task:
        if label not in task.labels and not any(lbl.id == label.id for lbl in task.labels):
            task.labels.append(label)
            await self.session.commit()
            await self.session.refresh(task)
        return task

    async def detach_label_from_task(self, task: Task, label: Label) -> Task:
        task.labels = [lbl for lbl in task.labels if lbl.id != label.id]
        await self.session.commit()
        await self.session.refresh(task)
        return task
