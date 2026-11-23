from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken
from app.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """Repository handling persistence and atomic operations for refresh tokens."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RefreshToken, session)

    async def create_token(
        self,
        jti: str,
        user_id: int,
        expires_at: datetime,
    ) -> RefreshToken:
        """Create and flush a new refresh token tracking record identified by its unique jti."""
        refresh_token = RefreshToken(
            jti=jti,
            user_id=user_id,
            expires_at=expires_at,
            revoked=False,
        )
        self.session.add(refresh_token)
        await self.session.flush()
        return refresh_token

    async def atomic_revoke_token(self, jti: str, now: datetime) -> int | None:
        """Atomically mark a valid, non-expired, non-revoked refresh token as revoked.

        Returns user_id if successfully revoked in this atomic operation, or None if already revoked/expired/missing.
        Works atomically across SQLite (3.35+) and PostgreSQL via UPDATE ... RETURNING.
        """
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.jti == jti,
                RefreshToken.revoked.is_(False),
                RefreshToken.expires_at > now,
            )
            .values(revoked=True)
            .returning(RefreshToken.user_id)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def get_by_jti(self, jti: str) -> RefreshToken | None:
        """Fetch a refresh token record by its jti identifier."""
        stmt = select(RefreshToken).where(RefreshToken.jti == jti)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def revoke_all_for_user(self, user_id: int) -> int:
        """Revoke all active refresh tokens for a user (e.g. on password change or reuse detection)."""
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return int(getattr(result, "rowcount", 0))

    async def cleanup_expired_tokens(self, now: datetime) -> int:
        """Purge expired refresh tokens from the database."""
        stmt = delete(RefreshToken).where(RefreshToken.expires_at <= now)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return int(getattr(result, "rowcount", 0))
