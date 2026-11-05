from app.core.constants import MSG_EMAIL_IN_USE, MSG_PASSWORD_MISMATCH
from app.core.exceptions import BadRequestException
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import ChangePassword, UserResponse, UserUpdate


class UserService:
    def __init__(self, user_repo: UserRepository) -> None:
        self.user_repo = user_repo

    async def get_profile(self, user: User) -> UserResponse:
        return UserResponse.model_validate(user)

    async def update_profile(self, user: User, update_in: UserUpdate) -> UserResponse:
        if update_in.email and update_in.email != user.email:
            existing = await self.user_repo.get_by_email(update_in.email)
            if existing and existing.id != user.id:
                raise BadRequestException(MSG_EMAIL_IN_USE)
            user.email = update_in.email

        if update_in.full_name is not None:
            user.full_name = update_in.full_name

        updated = await self.user_repo.update(user)
        return UserResponse.model_validate(updated)

    async def change_password(self, user: User, change_in: ChangePassword) -> None:
        if not verify_password(change_in.current_password, user.hashed_password):
            raise BadRequestException(MSG_PASSWORD_MISMATCH)
        user.hashed_password = hash_password(change_in.new_password)
        await self.user_repo.update(user)
