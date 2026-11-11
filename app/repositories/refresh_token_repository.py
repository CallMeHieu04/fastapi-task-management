from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken
from app.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """Repository handling persistence and atomic operations for refresh tokens."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RefreshToken, session)

    async def create_token(
        self,
        token: str,
        jti: str,
        user_id: int,
        expires_at: datetime,
    ) -> RefreshToken:
        """Create and persist a new refresh token."""
        refresh_token = RefreshToken(
            token=token,
            jti=jti,
            user_id=user_id,
            expires_at=expires_at,
            revoked=False,
        )
        self.session.add(refresh_token)
        await self.session.flush()
        return refresh_token

    async def get_by_token_for_update(self, token: str) -> RefreshToken | None:
        """Fetch a refresh token with row locking for atomic verification and rotation."""
        stmt = select(RefreshToken).where(RefreshToken.token == token).with_for_update()
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def revoke_token(self, token_obj: RefreshToken) -> None:
        """Mark a specific refresh token as revoked."""
        token_obj.revoked = True
        await self.session.flush()

    async def revoke_all_for_user(self, user_id: int) -> int:
        """Revoke all active refresh tokens for a user (e.g. on password change or token reuse)."""
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return int(getattr(result, "rowcount", 0))
