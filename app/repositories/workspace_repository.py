from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WorkspaceMemberRole
from app.models.workspace import Workspace, WorkspaceMember
from app.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Workspace, session)

    async def list_by_owner(self, owner_id: int) -> list[Workspace]:
        stmt = select(Workspace).where(Workspace.owner_id == owner_id).order_by(Workspace.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_member(self, workspace_id: int, user_id: int, role: WorkspaceMemberRole) -> WorkspaceMember:
        member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)
        self.session.add(member)
        await self.session.commit()
        await self.session.refresh(member)
        return member
