from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MSG_MEMBER_ALREADY_EXISTS
from app.core.exceptions import ConflictException
from app.models.enums import WorkspaceMemberRole
from app.models.workspace import Workspace, WorkspaceMember
from app.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    """Repository handling Workspace database queries and membership associations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Workspace, session)

    async def list_by_owner(self, owner_id: int) -> list[Workspace]:
        stmt = (
            select(Workspace)
            .where(Workspace.owner_id == owner_id)
            .order_by(Workspace.created_at.desc(), Workspace.id.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

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
        await self.session.flush()

        # Load workspace with eagerly-loaded members and member.user to avoid MissingGreenlet
        loaded = await self.get_by_id(workspace.id)
        assert loaded is not None
        return loaded

    async def list_by_user(
        self,
        user_id: int,
        page: int = DEFAULT_PAGE,
        limit: int = DEFAULT_PAGE_SIZE,
        search: str | None = None,
    ) -> tuple[list[Workspace], int]:
        """Fetch paginated workspaces where the user is an owner or member with optional name search."""
        base_query = (
            select(Workspace)
            .outerjoin(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(
                or_(
                    Workspace.owner_id == user_id,
                    WorkspaceMember.user_id == user_id,
                )
            )
        )
        if search:
            pattern = f"%{search.lower()}%"
            base_query = base_query.where(func.lower(Workspace.name).like(pattern))

        count_stmt = select(func.count()).select_from(base_query.distinct().subquery())
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = (
            base_query.distinct()
            .order_by(Workspace.created_at.desc(), Workspace.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        workspaces = list(result.scalars().all())
        return workspaces, total

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
        """Add a workspace membership. Raises ConflictException if already a member."""
        existing = await self.get_member(workspace_id, user_id)
        if existing:
            raise ConflictException(MSG_MEMBER_ALREADY_EXISTS)

        member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)
        self.session.add(member)
        try:
            await self.session.flush()
            await self.session.refresh(member)
            return member
        except IntegrityError as err:
            await self.session.rollback()
            raise ConflictException(MSG_MEMBER_ALREADY_EXISTS) from err

    async def remove_member(self, workspace_id: int, user_id: int) -> bool:
        """Remove membership record from a workspace."""
        member = await self.get_member(workspace_id, user_id)
        if member:
            await self.session.delete(member)
            await self.session.flush()
            return True
        return False
