from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic async repository pattern implementing standardized CRUD and pagination."""

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get_by_id(self, id: Any) -> ModelType | None:
        """Fetch a single record by primary key."""
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ModelType], int]:
        """Fetch paginated records along with total count."""
        count_stmt = select(func.count()).select_from(self.model)
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = select(self.model).offset(skip).limit(limit)
        res = await self.session.execute(stmt)
        items = list(res.scalars().all())
        return items, total

    async def create(self, instance: ModelType | None = None, **kwargs: Any) -> ModelType:
        """Create and persist a new model instance, accepting an instance or kwargs."""
        obj = instance if instance is not None else self.model(**kwargs)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update(self, instance: ModelType, **kwargs: Any) -> ModelType:
        """Update existing instance attributes and persist changes."""
        for field, value in kwargs.items():
            if hasattr(instance, field):
                setattr(instance, field, value)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def delete(self, instance: ModelType) -> None:
        """Delete instance from database."""
        await self.session.delete(instance)
        await self.session.commit()

    async def delete_by_id(self, id: Any) -> bool:
        """Delete record by ID. Returns True if deleted, False if not found."""
        instance = await self.get_by_id(id)
        if not instance:
            return False
        await self.delete(instance)
        return True
