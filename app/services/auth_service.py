import jwt

from app.core.cache import cache_service
from app.core.constants import (
    MSG_EMAIL_EXISTS,
    MSG_INVALID_CREDENTIALS,
    MSG_INVALID_TOKEN,
    MSG_INVALID_TOKEN_TYPE,
    MSG_TOKEN_REVOKED,
    MSG_USER_INACTIVE,
)
from app.core.exceptions import BadRequestException, ForbiddenException, UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserResponse


class AuthService:
    def __init__(self, user_repo: UserRepository) -> None:
        self.user_repo = user_repo

    async def register(self, user_in: UserCreate) -> UserResponse:
        existing = await self.user_repo.get_by_email(user_in.email)
        if existing:
            raise BadRequestException(MSG_EMAIL_EXISTS)

        user = User(
            email=user_in.email,
            full_name=user_in.full_name,
            hashed_password=hash_password(user_in.password),
            role=user_in.role or UserRole.MEMBER,
            is_active=True,
        )
        created_user = await self.user_repo.create(user)
        return UserResponse.model_validate(created_user)

    async def login(self, email: str, password: str) -> Token:
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedException(MSG_INVALID_CREDENTIALS)

        if not user.is_active:
            raise ForbiddenException(MSG_USER_INACTIVE)

        access_token = create_access_token(
            subject=user.id,
            extra_claims={"email": user.email, "role": user.role.value},
        )
        refresh_token = create_refresh_token(subject=user.id)

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    async def refresh_tokens(self, refresh_token: str) -> Token:
        if await cache_service.is_token_revoked(refresh_token):
            raise UnauthorizedException(MSG_TOKEN_REVOKED)

        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise UnauthorizedException(MSG_INVALID_TOKEN_TYPE)
            user_id = int(payload.get("sub", 0))
        except (jwt.PyJWTError, ValueError) as err:
            raise UnauthorizedException(MSG_INVALID_TOKEN) from err

        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedException(MSG_USER_INACTIVE)

        # Invalidate old refresh token (token rotation)
        await cache_service.revoke_token(refresh_token)

        new_access = create_access_token(
            subject=user.id,
            extra_claims={"email": user.email, "role": user.role.value},
        )
        new_refresh = create_refresh_token(subject=user.id)

        return Token(
            access_token=new_access,
            refresh_token=new_refresh,
            token_type="bearer",
        )

    async def logout(self, refresh_token: str) -> None:
        """Revoke the refresh token."""
        await cache_service.revoke_token(refresh_token)
