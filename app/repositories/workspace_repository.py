
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import WorkspaceMemberRole
from app.models.workspace import Workspace, WorkspaceMember


class WorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, workspace_id: int) -> Workspace | None:
        stmt = (
            select(Workspace)
            .where(Workspace.id == workspace_id)
            .options(
                selectinload(Workspace.members).joinedload(WorkspaceMember.user)
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_user(self, user_id: int) -> list[Workspace]:
        # Workspaces where user is a member
        stmt = (
            select(Workspace)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == user_id)
            .options(
                selectinload(Workspace.members).joinedload(WorkspaceMember.user)
            )
            .order_by(Workspace.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, name: str, owner_id: int) -> Workspace:
        workspace = Workspace(name=name, owner_id=owner_id)
        self.session.add(workspace)
        await self.session.flush()

        # Add owner to workspace_members as OWNER
        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=owner_id,
            role=WorkspaceMemberRole.OWNER,
        )
        self.session.add(member)
        await self.session.commit()
        return await self.get_by_id(workspace.id)  # type: ignore

    async def get_member(self, workspace_id: int, user_id: int) -> WorkspaceMember | None:
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def add_member(
        self, workspace_id: int, user_id: int, role: WorkspaceMemberRole
    ) -> WorkspaceMember:
        member = await self.get_member(workspace_id, user_id)
        if member:
            member.role = role
        else:
            member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)
            self.session.add(member)
        await self.session.commit()
        await self.session.refresh(member)
        return member

    async def remove_member(self, workspace_id: int, user_id: int) -> bool:
        member = await self.get_member(workspace_id, user_id)
        if not member:
            return False
        await self.session.delete(member)
        await self.session.commit()
        return True

    async def update(self, workspace: Workspace, name: str) -> Workspace:
        workspace.name = name
        await self.session.commit()
        await self.session.refresh(workspace)
        return workspace

    async def delete(self, workspace: Workspace) -> None:
        await self.session.delete(workspace)
        await self.session.commit()
