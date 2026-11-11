from sqlalchemy.exc import IntegrityError

from app.core.constants import (
    MSG_CANNOT_DELETE_LAST_ADMIN,
    MSG_CANNOT_DELETE_SELF,
    MSG_EMAIL_IN_USE,
    MSG_PASSWORD_MISMATCH,
    MSG_USER_NOT_FOUND,
)
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.core.security import hash_password, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import ChangePassword, UserResponse, UserUpdate


class UserService:
    """Service handling user profile management, security operations, and admin actions."""

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository,
    ) -> None:
        self.user_repo = user_repo
        self.token_repo = token_repo

    async def get_profile(self, user: User) -> UserResponse:
        """Get profile of current user."""
        return UserResponse.model_validate(user)

    async def update_profile(self, user: User, update_in: UserUpdate) -> UserResponse:
        """Update current user editable details."""
        if update_in.email is not None and update_in.email != user.email:
            user.email = update_in.email

        if update_in.full_name is not None:
            user.full_name = update_in.full_name

        try:
            updated = await self.user_repo.update(user)
            return UserResponse.model_validate(updated)
        except IntegrityError as err:
            await self.user_repo.session.rollback()
            raise ConflictException(MSG_EMAIL_IN_USE) from err

    async def change_password(self, user: User, change_in: ChangePassword) -> None:
        """Change user password and revoke all existing refresh tokens."""
        if not verify_password(change_in.current_password, user.hashed_password):
            raise BadRequestException(MSG_PASSWORD_MISMATCH)

        user.hashed_password = hash_password(change_in.new_password)
        await self.user_repo.update(user)

        # Invalidate all active refresh tokens for this user upon password change
        await self.token_repo.revoke_all_for_user(user.id)
        await self.user_repo.session.commit()

    async def get_user_by_id(self, user_id: int) -> UserResponse:
        """Get user details by ID (Admin or internal)."""
        target = await self.user_repo.get_by_id(user_id)
        if not target:
            raise NotFoundException(MSG_USER_NOT_FOUND.format(id=user_id))
        return UserResponse.model_validate(target)

    async def delete_user(self, current_admin: User, target_user_id: int) -> None:
        """Delete user account (Admin only). Prevents self-deletion and deleting last admin."""
        if current_admin.id == target_user_id:
            raise BadRequestException(MSG_CANNOT_DELETE_SELF)

        target = await self.user_repo.get_by_id(target_user_id)
        if not target:
            raise NotFoundException(MSG_USER_NOT_FOUND.format(id=target_user_id))

        if target.role == UserRole.ADMIN and target.is_active:
            admin_count = await self.user_repo.count_active_admins()
            if admin_count <= 1:
                raise BadRequestException(MSG_CANNOT_DELETE_LAST_ADMIN)

        # Revoke all tokens then delete user
        await self.token_repo.revoke_all_for_user(target_user_id)
        await self.user_repo.delete(target)
