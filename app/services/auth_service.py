from datetime import UTC, datetime

import jwt
from sqlalchemy.exc import IntegrityError

from app.core.constants import (
    MSG_EMAIL_EXISTS,
    MSG_INVALID_CREDENTIALS,
    MSG_INVALID_TOKEN,
    MSG_REFRESH_TOKEN_REQUIRED,
    MSG_TOKEN_EXPIRED,
    MSG_TOKEN_REUSED_REVOKED,
    MSG_USER_INACTIVE,
)
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    UnauthorizedException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import TokenType, UserRole
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserLogin, UserResponse


class AuthService:
    """Service encapsulating authentication, JWT lifecycle, and refresh token rotation."""

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository,
    ) -> None:
        self.user_repo = user_repo
        self.token_repo = token_repo

    async def register(self, user_in: UserCreate) -> UserResponse:
        """Register a new user. Enforces MEMBER role and catches IntegrityError for 409."""
        user = User(
            email=user_in.email,
            full_name=user_in.full_name,
            hashed_password=hash_password(user_in.password),
            role=UserRole.MEMBER,  # Role is strictly assigned by backend
            is_active=True,
        )
        try:
            created_user = await self.user_repo.create(user)
            return UserResponse.model_validate(created_user)
        except IntegrityError as err:
            await self.user_repo.session.rollback()
            raise ConflictException(MSG_EMAIL_EXISTS) from err

    async def login(self, login_data: UserLogin) -> Token:
        """Authenticate user and issue access/refresh token pair."""
        user = await self.user_repo.get_by_email(login_data.email)
        if not user or not verify_password(login_data.password, user.hashed_password):
            raise UnauthorizedException(MSG_INVALID_CREDENTIALS)

        if not user.is_active:
            raise ForbiddenException(MSG_USER_INACTIVE)

        access_token = create_access_token(
            subject=user.id,
            extra_claims={"email": user.email, "role": user.role.value},
        )
        refresh_token, jti, expires_at = create_refresh_token(subject=user.id)

        await self.token_repo.create_token(
            token=refresh_token,
            jti=jti,
            user_id=user.id,
            expires_at=expires_at,
        )
        await self.token_repo.session.commit()

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    async def refresh_tokens(self, refresh_token: str) -> Token:
        """Atomic refresh token rotation with reuse detection."""
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != TokenType.REFRESH.value:
                raise UnauthorizedException(MSG_REFRESH_TOKEN_REQUIRED)
            sub_raw = payload.get("sub")
            if sub_raw is None:
                raise UnauthorizedException(MSG_INVALID_TOKEN)
            user_id = int(sub_raw)
        except (jwt.PyJWTError, ValueError, KeyError) as err:
            raise UnauthorizedException(MSG_INVALID_TOKEN) from err

        db_token = await self.token_repo.get_by_token_for_update(refresh_token)
        if not db_token:
            raise UnauthorizedException(MSG_INVALID_TOKEN)

        # Token reuse detection
        if db_token.revoked:
            await self.token_repo.revoke_all_for_user(db_token.user_id)
            await self.token_repo.session.commit()
            raise UnauthorizedException(MSG_TOKEN_REUSED_REVOKED)

        # Check expiration (ensure timezone aware comparison)
        expires_at = db_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < datetime.now(UTC):
            await self.token_repo.revoke_token(db_token)
            await self.token_repo.session.commit()
            raise UnauthorizedException(MSG_TOKEN_EXPIRED)

        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedException(MSG_USER_INACTIVE)

        # Atomic rotation: revoke old token and create new token pair in one transaction
        await self.token_repo.revoke_token(db_token)

        new_access = create_access_token(
            subject=user.id,
            extra_claims={"email": user.email, "role": user.role.value},
        )
        new_refresh, new_jti, new_expires = create_refresh_token(subject=user.id)

        await self.token_repo.create_token(
            token=new_refresh,
            jti=new_jti,
            user_id=user.id,
            expires_at=new_expires,
        )
        await self.token_repo.session.commit()

        return Token(
            access_token=new_access,
            refresh_token=new_refresh,
            token_type="bearer",
        )

    async def logout(self, refresh_token: str) -> None:
        """Revoke refresh token on logout."""
        db_token = await self.token_repo.get_by_token_for_update(refresh_token)
        if db_token and not db_token.revoked:
            await self.token_repo.revoke_token(db_token)
            await self.token_repo.session.commit()
