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
    summary="Register a new user account",
    responses={
        409: {"description": "Email already exists"},
        422: {"description": "Validation error"},
    },
)
async def register(
    user_in: UserCreate,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    """Register a new account. Role is assigned automatically by the system as MEMBER."""
    return await auth_service.register(user_in=user_in)


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive JWT token pair",
    responses={
        401: {"description": "Incorrect email or password"},
        403: {"description": "Inactive account"},
    },
)
async def login(
    login_data: UserLogin,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Token:
    """Log in with email and password to receive access and refresh tokens."""
    return await auth_service.login(login_data=login_data)


@router.post(
    "/refresh",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token for a new token pair",
    responses={
        401: {"description": "Invalid, expired, or reused refresh token"},
    },
)
async def refresh_tokens(
    refresh_in: RefreshTokenRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Token:
    """Exchange an active refresh token for a newly rotated access/refresh pair."""
    return await auth_service.refresh_tokens(refresh_token=refresh_in.refresh_token)


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout and revoke refresh token",
)
async def logout(
    refresh_in: RefreshTokenRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    """Revoke the given refresh token on logout."""
    await auth_service.logout(refresh_token=refresh_in.refresh_token)
    return MessageResponse(message="Successfully logged out.")
