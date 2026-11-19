from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.deps import CurrentAdmin, CurrentUser, get_user_service
from app.schemas.common import MessageResponse
from app.schemas.user import ChangePassword, UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
)
async def get_my_profile(
    current_user: CurrentUser,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    """Retrieve details of the currently authenticated user."""
    return await user_service.get_profile(user=current_user)


@router.patch(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update current user profile",
)
async def update_my_profile(
    user_update: UserUpdate,
    current_user: CurrentUser,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    """Update profile fields (full_name, email) of the authenticated user."""
    return await user_service.update_profile(user=current_user, update_in=user_update)


@router.post(
    "/me/change-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Change account password",
)
async def change_my_password(
    change_pwd: ChangePassword,
    current_user: CurrentUser,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> MessageResponse:
    """Update password for current user and revoke all their active refresh tokens."""
    await user_service.change_password(user=current_user, change_in=change_pwd)
    return MessageResponse(message="Password changed successfully.")


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user account (Admin only)",
    responses={
        400: {"description": "Cannot delete self or last active admin"},
        403: {"description": "Admin privileges required"},
        404: {"description": "User not found"},
    },
)
async def delete_user(
    id: Annotated[int, Path(ge=1, description="Target user ID to delete")],
    current_admin: CurrentAdmin,
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    """Permanently delete a user account. Restricted to administrators."""
    await user_service.delete_user(current_admin=current_admin, target_user_id=id)
