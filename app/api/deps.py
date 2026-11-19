from datetime import datetime
from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheService, cache_service
from app.core.constants import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MSG_ADMIN_REQUIRED,
    MSG_INVALID_CREDENTIALS,
    MSG_NOT_AUTHENTICATED,
    MSG_USER_INACTIVE,
)
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_token_claim
from app.db.session import get_db
from app.models.enums import ProjectStatus, TaskPriority, TaskStatus, TokenType, UserRole
from app.models.user import User
from app.repositories.comment_repository import CommentRepository
from app.repositories.label_repository import LabelRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.services.auth_service import AuthService
from app.services.comment_service import CommentService
from app.services.label_service import LabelService
from app.services.project_service import ProjectService
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.services.workspace_service import WorkspaceService

# Bearer token security scheme for OpenAPI with auto_error=False to route missing auth through custom exception handler
security_scheme = HTTPBearer(auto_error=False)

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


def get_project_repository(session: DbSession) -> ProjectRepository:
    """Dependency provider for ProjectRepository."""
    return ProjectRepository(session=session)


def get_label_repository(session: DbSession) -> LabelRepository:
    """Dependency provider for LabelRepository."""
    return LabelRepository(session=session)


def get_comment_repository(session: DbSession) -> CommentRepository:
    """Dependency provider for CommentRepository."""
    return CommentRepository(session=session)


# ==============================================================================
# Authentication & User Dependencies
# ==============================================================================


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    """Decode access token and fetch current active user.

    Strictly validates token claim type and catches KeyError/ValueError on subject parsing.
    """
    if not credentials:
        raise UnauthorizedException(MSG_NOT_AUTHENTICATED)

    token = credentials.credentials
    user_id, _ = decode_token_claim(token, TokenType.ACCESS.value)

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


def get_cache_service() -> CacheService:
    """Dependency provider for CacheService."""
    return cache_service


def get_workspace_service(
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> WorkspaceService:
    """Dependency provider for WorkspaceService."""
    return WorkspaceService(workspace_repo=workspace_repo, user_repo=user_repo, cache_service=cache)


def get_project_service(
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> ProjectService:
    """Dependency provider for ProjectService."""
    return ProjectService(project_repo=project_repo, workspace_service=workspace_service, cache_service=cache)


def get_task_service(
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> TaskService:
    """Dependency provider for TaskService."""
    return TaskService(
        repository=repository,
        project_repo=project_repo,
        workspace_service=workspace_service,
        user_repo=user_repo,
        cache_service=cache,
    )


def get_label_service(
    label_repo: Annotated[LabelRepository, Depends(get_label_repository)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    task_repo: Annotated[TaskRepository, Depends(get_task_repository)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> LabelService:
    """Dependency provider for LabelService."""
    return LabelService(
        label_repo=label_repo,
        project_repo=project_repo,
        task_repo=task_repo,
        workspace_service=workspace_service,
        cache_service=cache,
    )


def get_comment_service(
    comment_repo: Annotated[CommentRepository, Depends(get_comment_repository)],
    task_repo: Annotated[TaskRepository, Depends(get_task_repository)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> CommentService:
    """Dependency provider for CommentService."""
    return CommentService(
        comment_repo=comment_repo,
        task_repo=task_repo,
        project_repo=project_repo,
        workspace_service=workspace_service,
    )


# ==============================================================================
# Filter & Query Parameters
# ==============================================================================


class PaginationParams:
    """Query parameter dependency for paginated listing."""

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="Page number starting at 1")] = DEFAULT_PAGE,
        limit: Annotated[
            int, Query(ge=1, le=MAX_PAGE_SIZE, description=f"Items per page (max {MAX_PAGE_SIZE})")
        ] = DEFAULT_PAGE_SIZE,
    ):
        self.page = page
        self.limit = limit


class WorkspaceFilterParams:
    """Query parameter dependency for workspace listing with search and pagination."""

    def __init__(
        self,
        search: Annotated[str | None, Query(max_length=50, description="Keyword search in workspace name")] = None,
        page: Annotated[int, Query(ge=1, description="Page number starting at 1")] = DEFAULT_PAGE,
        limit: Annotated[
            int, Query(ge=1, le=MAX_PAGE_SIZE, description=f"Items per page (max {MAX_PAGE_SIZE})")
        ] = DEFAULT_PAGE_SIZE,
    ):
        self.search = search
        self.page = page
        self.limit = limit


class ProjectFilterParams:
    """Query parameter dependency for project listing with filtering, search, and pagination."""

    def __init__(
        self,
        search: Annotated[str | None, Query(max_length=50, description="Keyword search in name/desc")] = None,
        status: Annotated[
            ProjectStatus | None, Query(description="Filter by project status (ACTIVE, ARCHIVED)")
        ] = None,
        sort_by: Annotated[
            str, Query(description="Field to sort by: created_at, name, status, updated_at")
        ] = "created_at",
        order: Annotated[str, Query(pattern="^(asc|desc)$", description="Sort order: asc or desc")] = "desc",
        page: Annotated[int, Query(ge=1, description="Page number starting at 1")] = DEFAULT_PAGE,
        limit: Annotated[
            int, Query(ge=1, le=MAX_PAGE_SIZE, description=f"Items per page (max {MAX_PAGE_SIZE})")
        ] = DEFAULT_PAGE_SIZE,
    ):
        self.search = search
        self.status = status
        self.sort_by = sort_by
        self.order = order
        self.page = page
        self.limit = limit


class TaskFilterParams:
    """Query parameter dependency for task listing with filtering, searching, sorting, and pagination."""

    def __init__(
        self,
        status: Annotated[TaskStatus | None, Query(description="Filter by task status")] = None,
        priority: Annotated[TaskPriority | None, Query(description="Filter by priority")] = None,
        search: Annotated[str | None, Query(max_length=50, description="Keyword search in title/desc")] = None,
        project_id: Annotated[int | None, Query(description="Filter by project ID")] = None,
        assignee_id: Annotated[int | None, Query(description="Filter by assignee user ID")] = None,
        label_id: Annotated[int | None, Query(description="Filter by attached label ID")] = None,
        due_date_from: Annotated[datetime | None, Query(description="Filter tasks due on or after date")] = None,
        due_date_to: Annotated[datetime | None, Query(description="Filter tasks due on or before date")] = None,
        sort_by: Annotated[
            str, Query(description="Field to sort by: created_at, due_date, priority, title, status, updated_at")
        ] = "created_at",
        order: Annotated[str, Query(pattern="^(asc|desc)$", description="Sort order: asc or desc")] = "desc",
        page: Annotated[int, Query(ge=1, description="Page number starting at 1")] = DEFAULT_PAGE,
        limit: Annotated[
            int, Query(ge=1, le=MAX_PAGE_SIZE, description=f"Items per page (max {MAX_PAGE_SIZE})")
        ] = DEFAULT_PAGE_SIZE,
    ):
        self.status = status
        self.priority = priority
        self.search = search
        self.project_id = project_id
        self.assignee_id = assignee_id
        self.label_id = label_id
        self.due_date_from = due_date_from
        self.due_date_to = due_date_to
        self.sort_by = sort_by
        self.order = order
        self.page = page
        self.limit = limit
