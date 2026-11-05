
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.label import Label
from app.schemas.label import LabelCreate


class LabelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, label_id: int) -> Label | None:
        result = await self.session.execute(select(Label).where(Label.id == label_id))
        return result.scalars().first()

    async def list_by_project(self, project_id: int) -> list[Label]:
        result = await self.session.execute(
            select(Label).where(Label.project_id == project_id)
        )
        return list(result.scalars().all())

    async def create(self, project_id: int, label_in: LabelCreate) -> Label:
        label = Label(
            project_id=project_id,
            name=label_in.name,
            color=label_in.color,
        )
        self.session.add(label)
        await self.session.commit()
        await self.session.refresh(label)
        return label

    async def delete(self, label: Label) -> None:
        await self.session.delete(label)
        await self.session.commit()
