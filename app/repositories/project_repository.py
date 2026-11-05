from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProjectStatus
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, project_id: int) -> Project | None:
        result = await self.session.execute(select(Project).where(Project.id == project_id))
        return result.scalars().first()

    async def list_by_workspace(self, workspace_id: int) -> list[Project]:
        stmt = select(Project).where(Project.workspace_id == workspace_id).order_by(Project.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, workspace_id: int, project_in: ProjectCreate) -> Project:
        project = Project(
            workspace_id=workspace_id,
            name=project_in.name,
            description=project_in.description,
            status=ProjectStatus.ACTIVE,
        )
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def update(self, project: Project, project_in: ProjectUpdate) -> Project:
        update_data = project_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def delete(self, project: Project) -> None:
        await self.session.delete(project)
        await self.session.commit()
