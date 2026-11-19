from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.label import Label
from app.models.task import Task
from app.repositories.base import BaseRepository


class LabelRepository(BaseRepository[Label]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Label, session)

    async def get_by_project_and_name(self, project_id: int, name: str) -> Label | None:
        """Fetch a label by its parent project ID and name."""
        stmt = select(Label).where(Label.project_id == project_id, Label.name == name)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_project(self, project_id: int) -> list[Label]:
        """Fetch all labels for a project sorted alphabetically with stable tie-breaker."""
        stmt = select(Label).where(Label.project_id == project_id).order_by(Label.name.asc(), Label.id.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def attach_label_to_task(self, task: Task, label: Label) -> Task:
        """Attach label to task and flush changes."""
        task.labels.append(label)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def detach_label_from_task(self, task: Task, label: Label) -> Task:
        """Detach label from task and flush changes."""
        task.labels = [lbl for lbl in task.labels if lbl.id != label.id]
        await self.session.flush()
        await self.session.refresh(task)
        return task
