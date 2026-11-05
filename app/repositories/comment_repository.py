
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
from app.schemas.comment import CommentCreate


class CommentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, comment_id: int) -> Comment | None:
        stmt = (
            select(Comment)
            .where(Comment.id == comment_id)
            .options(selectinload(Comment.author), selectinload(Comment.task))
        )
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

    async def create(self, task_id: int, author_id: int, comment_in: CommentCreate) -> Comment:
        comment = Comment(
            task_id=task_id,
            author_id=author_id,
            content=comment_in.content,
        )
        self.session.add(comment)
        await self.session.commit()
        return await self.get_by_id(comment.id)  # type: ignore

    async def delete(self, comment: Comment) -> None:
        await self.session.delete(comment)
        await self.session.commit()
