from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
from app.repositories.base import BaseRepository


class CommentRepository(BaseRepository[Comment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Comment, session)

    async def get_by_id(self, id: int) -> Comment | None:
        stmt = select(Comment).where(Comment.id == id).options(selectinload(Comment.author))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_task(self, task_id: int) -> list[Comment]:
        stmt = (
            select(Comment)
            .where(Comment.task_id == task_id)
            .options(selectinload(Comment.author))
            .order_by(Comment.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
