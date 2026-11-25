from datetime import UTC, datetime

from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError

from app.core.constants import (
    MSG_EMAIL_EXISTS,
    MSG_INVALID_CREDENTIALS,
    MSG_INVALID_TOKEN,
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
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    decode_token_claim,
    hash_password,
    verify_password_async,
)
from app.models.enums import TokenType, UserRole
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.services.notification_service import NotificationService


class AuthService:
    """Service encapsulating authentication, JWT lifecycle, and refresh token rotation."""

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository,
    ) -> None:
        self.user_repo = user_repo
        self.token_repo = token_repo

    async def register(
        self,
        user_in: UserCreate,
        background_tasks: BackgroundTasks | None = None,
    ) -> UserResponse:
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
        except IntegrityError as err:
            await self.user_repo.session.rollback()
            raise ConflictException(MSG_EMAIL_EXISTS) from err

        if background_tasks:
            background_tasks.add_task(NotificationService.send_welcome_email, user_id=created_user.id)
        return UserResponse.model_validate(created_user)

    async def login(self, login_data: UserLogin) -> Token:
        """Authenticate user and issue access/refresh token pair.

        Protects against timing attacks by hashing a dummy payload when user is not found,
        and offloads bcrypt verification to a threadpool.
        """
        user = await self.user_repo.get_by_email(login_data.email)
        if user:
            is_valid = await verify_password_async(login_data.password, user.hashed_password)
        else:
            await verify_password_async(login_data.password, DUMMY_PASSWORD_HASH)
            is_valid = False

        if not user or not is_valid:
            raise UnauthorizedException(MSG_INVALID_CREDENTIALS)

        if not user.is_active:
            raise ForbiddenException(MSG_USER_INACTIVE)

        access_token = create_access_token(
            subject=user.id,
            extra_claims={"email": user.email, "role": user.role.value},
        )
        refresh_token, jti, expires_at = create_refresh_token(subject=user.id)

        await self.token_repo.create_token(
            jti=jti,
            user_id=user.id,
            expires_at=expires_at,
        )

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    async def refresh_tokens(self, refresh_token: str) -> Token:
        """Atomic refresh token rotation with reuse detection via UPDATE ... RETURNING."""
        user_id, jti = decode_token_claim(refresh_token, TokenType.REFRESH.value)

        now = datetime.now(UTC)
        # 1. Attempt atomic revocation in 1 statement
        revoked_user_id = await self.token_repo.atomic_revoke_token(jti=jti, now=now)

        if revoked_user_id is None:
            # Atomic revocation failed -> investigate reason (reuse, expired, or missing)
            db_token = await self.token_repo.get_by_jti(jti)
            if not db_token:
                raise UnauthorizedException(MSG_INVALID_TOKEN)

            if db_token.revoked:
                # Token reuse detected! Revoke all active sessions for this user
                await self.token_repo.revoke_all_for_user(db_token.user_id)
                await self.token_repo.session.commit()
                raise UnauthorizedException(MSG_TOKEN_REUSED_REVOKED)

            expires_at = db_token.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)

            if expires_at <= now:
                raise UnauthorizedException(MSG_TOKEN_EXPIRED)

            raise UnauthorizedException(MSG_INVALID_TOKEN)

        # 2. Token successfully revoked atomically. Fetch user and verify active status.
        user = await self.user_repo.get_by_id(revoked_user_id)
        if not user:
            raise UnauthorizedException(MSG_INVALID_CREDENTIALS)

        if not user.is_active:
            raise ForbiddenException(MSG_USER_INACTIVE)

        # 3. Issue new token pair
        new_access = create_access_token(
            subject=user.id,
            extra_claims={"email": user.email, "role": user.role.value},
        )
        new_refresh, new_jti, new_expires = create_refresh_token(subject=user.id)

        await self.token_repo.create_token(
            jti=new_jti,
            user_id=user.id,
            expires_at=new_expires,
        )

        return Token(
            access_token=new_access,
            refresh_token=new_refresh,
            token_type="bearer",
        )

    async def logout(self, refresh_token: str) -> None:
        """Revoke refresh token on logout."""
        try:
            _, jti = decode_token_claim(refresh_token, TokenType.REFRESH.value)
            await self.token_repo.atomic_revoke_token(jti=jti, now=datetime.now(UTC))
        except UnauthorizedException:
            pass
