from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from app.models.project import Project
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Project, session)

    async def list_by_workspace(
        self,
        workspace_id: int,
        page: int = DEFAULT_PAGE,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[Project], int]:
        """Fetch paginated projects within a workspace with stable tie-breaker sorting."""
        count_stmt = select(func.count(Project.id)).where(Project.workspace_id == workspace_id)
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = (
            select(Project)
            .where(Project.workspace_id == workspace_id)
            .order_by(Project.created_at.desc(), Project.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
