from typing import Annotated

import jwt
from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MSG_ACCESS_TOKEN_REQUIRED,
    MSG_ADMIN_REQUIRED,
    MSG_COULD_NOT_VALIDATE,
    MSG_INVALID_CREDENTIALS,
    MSG_USER_INACTIVE,
)
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import TaskPriority, TaskStatus, TokenType, UserRole
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.services.auth_service import AuthService
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.services.workspace_service import WorkspaceService

# Bearer token security scheme for OpenAPI
security_scheme = HTTPBearer(auto_error=True)

# Annotated Type Alias for DB Session
DbSession = Annotated[AsyncSession, Depends(get_db)]


# ==============================================================================
# Repository Providers
# ==============================================================================


def get_user_repository(session: DbSession) -> UserRepository:
    """Dependency provider for UserRepository."""
    return UserRepository(session=session)


def get_refresh_token_repository(session: DbSession) -> RefreshTokenRepository:
    """Dependency provider for RefreshTokenRepository."""
    return RefreshTokenRepository(session=session)


def get_task_repository(session: DbSession) -> TaskRepository:
    """Dependency provider for TaskRepository."""
    return TaskRepository(session=session)


def get_workspace_repository(session: DbSession) -> WorkspaceRepository:
    """Dependency provider for WorkspaceRepository."""
    return WorkspaceRepository(session=session)


# ==============================================================================
# Authentication & User Dependencies
# ==============================================================================


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security_scheme)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    """Decode access token and fetch current active user.

    Strictly validates token claim type and catches KeyError/ValueError on subject parsing.
    """
    token = credentials.credentials
    try:
        payload = decode_token(token)
        token_type = payload.get("type")
        if token_type != TokenType.ACCESS.value:
            raise UnauthorizedException(MSG_ACCESS_TOKEN_REQUIRED)
        sub_raw = payload.get("sub")
        if sub_raw is None:
            raise UnauthorizedException(MSG_COULD_NOT_VALIDATE)
        user_id = int(sub_raw)
    except (jwt.PyJWTError, ValueError, KeyError) as err:
        raise UnauthorizedException(MSG_COULD_NOT_VALIDATE) from err

    user = await user_repo.get_by_id(user_id)
    if not user:
        raise UnauthorizedException(MSG_INVALID_CREDENTIALS)

    if not user.is_active:
        raise ForbiddenException(MSG_USER_INACTIVE)

    return user


async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Ensure currently authenticated user possesses ADMIN privileges."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenException(MSG_ADMIN_REQUIRED)
    return current_user


# Annotated Type Aliases for Current User & Admin
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdmin = Annotated[User, Depends(get_current_admin_user)]


# ==============================================================================
# Service Providers
# ==============================================================================


def get_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    token_repo: Annotated[RefreshTokenRepository, Depends(get_refresh_token_repository)],
) -> AuthService:
    """Dependency provider for AuthService."""
    return AuthService(user_repo=user_repo, token_repo=token_repo)


def get_user_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    token_repo: Annotated[RefreshTokenRepository, Depends(get_refresh_token_repository)],
) -> UserService:
    """Dependency provider for UserService."""
    return UserService(user_repo=user_repo, token_repo=token_repo)


def get_workspace_service(
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> WorkspaceService:
    """Dependency provider for WorkspaceService."""
    return WorkspaceService(workspace_repo=workspace_repo, user_repo=user_repo)


def get_task_service(
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskService:
    """Dependency provider for TaskService."""
    return TaskService(repository=repository)


# ==============================================================================
# Filter & Query Parameters
# ==============================================================================


class TaskFilterParams:
    """Query parameter dependency for task listing with filtering and pagination."""

    def __init__(
        self,
        status: Annotated[TaskStatus | None, Query(description="Filter by task status")] = None,
        priority: Annotated[TaskPriority | None, Query(description="Filter by priority")] = None,
        search: Annotated[str | None, Query(max_length=50, description="Keyword search in title/desc")] = None,
        page: Annotated[int, Query(ge=1, description="Page number starting at 1")] = DEFAULT_PAGE,
        limit: Annotated[
            int, Query(ge=1, le=MAX_PAGE_SIZE, description=f"Items per page (max {MAX_PAGE_SIZE})")
        ] = DEFAULT_PAGE_SIZE,
    ):
        self.status = status
        self.priority = priority
        self.search = search
        self.page = page
        self.limit = limit
