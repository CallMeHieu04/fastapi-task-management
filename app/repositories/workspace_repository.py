from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import WorkspaceMemberRole
from app.models.workspace import Workspace, WorkspaceMember
from app.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    """Repository handling Workspace database queries and membership associations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Workspace, session)

    async def get_by_id(self, id: Any) -> Workspace | None:
        """Fetch a single workspace by primary key with members refreshed."""
        stmt = (
            select(Workspace)
            .where(Workspace.id == id)
            .options(selectinload(Workspace.members).selectinload(WorkspaceMember.user))
            .execution_options(populate_existing=True)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_workspace(self, name: str, owner_id: int) -> Workspace:
        """Create a workspace and automatically assign the owner as an OWNER member."""
        workspace = Workspace(name=name, owner_id=owner_id)
        self.session.add(workspace)
        await self.session.flush()

        # Add creator as OWNER member
        owner_member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=owner_id,
            role=WorkspaceMemberRole.OWNER,
        )
        self.session.add(owner_member)
        await self.session.commit()
        await self.session.refresh(workspace)
        return workspace

    async def list_by_user(self, user_id: int) -> list[Workspace]:
        """Fetch all workspaces where the user is an owner or member."""
        stmt = (
            select(Workspace)
            .outerjoin(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(
                or_(
                    Workspace.owner_id == user_id,
                    WorkspaceMember.user_id == user_id,
                )
            )
            .distinct()
            .order_by(Workspace.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_member(self, workspace_id: int, user_id: int) -> WorkspaceMember | None:
        """Find membership record for a specific user in a workspace."""
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def add_member(
        self,
        workspace_id: int,
        user_id: int,
        role: WorkspaceMemberRole,
    ) -> WorkspaceMember:
        """Add or update a workspace membership."""
        existing = await self.get_member(workspace_id, user_id)
        if existing:
            existing.role = role
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)
        self.session.add(member)
        await self.session.commit()
        await self.session.refresh(member)
        return member

    async def remove_member(self, workspace_id: int, user_id: int) -> bool:
        """Remove membership record from a workspace."""
        member = await self.get_member(workspace_id, user_id)
        if member:
            await self.session.delete(member)
            await self.session.commit()
            return True
        return False
