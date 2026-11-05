from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user, get_user_service
from app.models.user import User
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
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    """Retrieve details of the currently authenticated user."""
    return await service.get_profile(current_user)


@router.patch(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update profile details",
)
async def update_my_profile(
    user_update: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    """Update editable fields (full_name, email) of the current user."""
    return await service.update_profile(current_user, user_update)


@router.post(
    "/me/change-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Change account password",
)
async def change_my_password(
    change_pwd: ChangePassword,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> MessageResponse:
    """Change the password for the current user."""
    await service.change_password(current_user, change_pwd)
    return MessageResponse(message="Password changed successfully.")
