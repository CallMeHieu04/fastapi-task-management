from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import get_auth_service
from app.schemas.common import MessageResponse
from app.schemas.token import RefreshTokenRequest, Token
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={
        400: {"description": "Email already exists"},
        422: {"description": "Validation error"},
    },
)
async def register(
    user_in: UserCreate,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    """Register a new user account."""
    return await service.register(user_in)


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Login to receive access and refresh tokens",
    responses={
        401: {"description": "Incorrect email or password"},
        403: {"description": "Inactive user account"},
    },
)
async def login(
    login_data: UserLogin,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Token:
    """Authenticate with email and password to receive JWT tokens."""
    return await service.login(login_data.email, login_data.password)


@router.post(
    "/refresh",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token using refresh token",
    responses={
        401: {"description": "Invalid, expired, or revoked refresh token"},
    },
)
async def refresh_token(
    refresh_in: RefreshTokenRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Token:
    """Exchange a valid refresh token for a newly issued access token."""
    return await service.refresh_tokens(refresh_in.refresh_token)


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout and revoke refresh token",
)
async def logout(
    refresh_in: RefreshTokenRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    """Revoke refresh token so it cannot be used again."""
    await service.logout(refresh_in.refresh_token)
    return MessageResponse(message="Successfully logged out and revoked refresh token.")
