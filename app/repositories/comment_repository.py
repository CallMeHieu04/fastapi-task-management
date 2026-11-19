from sqlalchemy import func, select
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

    async def list_by_task(
        self,
        task_id: int,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Comment], int]:
        """Fetch paginated comments for a task sorted chronologically with tie-breaker."""
        base_query = select(Comment).where(Comment.task_id == task_id)

        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = (
            base_query.options(selectinload(Comment.author))
            .order_by(Comment.created_at.asc(), Comment.id.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
