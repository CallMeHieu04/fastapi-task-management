from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from app.models.enums import ProjectStatus
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
        search: str | None = None,
        status: ProjectStatus | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> tuple[list[Project], int]:
        """Fetch paginated projects within a workspace with search, filtering, and stable sorting."""
        query = select(Project).where(Project.workspace_id == workspace_id)

        if status is not None:
            query = query.where(Project.status == status)
        if search:
            pattern = f"%{search.lower()}%"
            query = query.where(
                (func.lower(Project.name).like(pattern)) | (func.lower(Project.description).like(pattern))
            )

        count_stmt = select(func.count()).select_from(query.subquery())
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        sort_by_str = sort_by.value if hasattr(sort_by, "value") else str(sort_by)
        order_str = order.value if hasattr(order, "value") else str(order)

        sort_column_map = {
            "created_at": Project.created_at,
            "name": Project.name,
            "status": Project.status,
        }
        col = sort_column_map.get(sort_by_str, Project.created_at)
        sort_expr = col.asc() if order_str.lower() == "asc" else col.desc()

        stmt = query.order_by(sort_expr, Project.id.desc()).offset((page - 1) * limit).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
