from typing import Annotated

import jwt
from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import TaskPriority, TaskStatus, UserRole
from app.models.user import User
from app.repositories.comment_repository import CommentRepository
from app.repositories.label_repository import LabelRepository
from app.repositories.project_repository import ProjectRepository
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

# Swagger Bearer authentication scheme
security_scheme = HTTPBearer(auto_error=True)


# ==============================================================================
# Repository Dependencies (Injectable for unit testing)
# ==============================================================================


def get_user_repository(session: Annotated[AsyncSession, Depends(get_db)]) -> UserRepository:
    return UserRepository(session)


def get_workspace_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceRepository:
    return WorkspaceRepository(session)


def get_project_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectRepository:
    return ProjectRepository(session)


def get_task_repository(session: Annotated[AsyncSession, Depends(get_db)]) -> TaskRepository:
    return TaskRepository(session)


def get_label_repository(session: Annotated[AsyncSession, Depends(get_db)]) -> LabelRepository:
    return LabelRepository(session)


def get_comment_repository(session: Annotated[AsyncSession, Depends(get_db)]) -> CommentRepository:
    return CommentRepository(session)


# ==============================================================================
# Authentication & User Dependencies
# ==============================================================================


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security_scheme)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    """Dependency to retrieve and validate the authenticated user from JWT Bearer token."""
    token = credentials.credentials
    try:
        payload = decode_token(token)
        token_type = payload.get("type")
        if token_type != "access":
            raise UnauthorizedException("Invalid token type. Access token expected.")
        user_id = int(payload.get("sub", 0))
    except (jwt.PyJWTError, ValueError) as err:
        raise UnauthorizedException("Could not validate credentials.") from err

    user = await user_repo.get_by_id(user_id)
    if not user:
        raise UnauthorizedException("User not found.")
    if not user.is_active:
        raise ForbiddenException("Inactive user account.")
    return user


async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Dependency ensuring current authenticated user has ADMIN role."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenException("The user doesn't have sufficient privileges (ADMIN required).")
    return current_user


# ==============================================================================
# Service Provider Dependencies (Pure Dependency Injection)
# ==============================================================================


def get_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthService:
    return AuthService(user_repo=user_repo)


def get_user_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    return UserService(user_repo=user_repo)


def get_workspace_service(
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> WorkspaceService:
    return WorkspaceService(workspace_repo=workspace_repo, user_repo=user_repo)


def get_project_service(
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> ProjectService:
    return ProjectService(
        project_repo=project_repo,
        workspace_service=workspace_service,
    )


def get_task_service(
    task_repo: Annotated[TaskRepository, Depends(get_task_repository)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    label_repo: Annotated[LabelRepository, Depends(get_label_repository)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> TaskService:
    return TaskService(
        task_repo=task_repo,
        project_repo=project_repo,
        user_repo=user_repo,
        label_repo=label_repo,
        workspace_service=workspace_service,
    )


def get_label_service(
    label_repo: Annotated[LabelRepository, Depends(get_label_repository)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> LabelService:
    return LabelService(
        label_repo=label_repo,
        project_repo=project_repo,
        workspace_service=workspace_service,
    )


def get_comment_service(
    comment_repo: Annotated[CommentRepository, Depends(get_comment_repository)],
    task_repo: Annotated[TaskRepository, Depends(get_task_repository)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> CommentService:
    return CommentService(
        comment_repo=comment_repo,
        task_repo=task_repo,
        project_repo=project_repo,
        workspace_service=workspace_service,
    )


class TaskFilterParams:
    """Query parameter dependency for task listing with filtering and pagination."""

    def __init__(
        self,
        status: Annotated[TaskStatus | None, Query(description="Filter by task status")] = None,
        priority: Annotated[TaskPriority | None, Query(description="Filter by priority")] = None,
        assignee_id: Annotated[int | None, Query(description="Filter by assigned user ID")] = None,
        page: Annotated[int, Query(ge=1, description="Page number starting at 1")] = DEFAULT_PAGE,
        limit: Annotated[
            int, Query(ge=1, le=MAX_PAGE_SIZE, description=f"Items per page (max {MAX_PAGE_SIZE})")
        ] = DEFAULT_PAGE_SIZE,
    ):
        self.status = status
        self.priority = priority
        self.assignee_id = assignee_id
        self.page = page
        self.limit = limit
