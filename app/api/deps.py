from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import TaskPriority, TaskStatus, UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.comment_service import CommentService
from app.services.label_service import LabelService
from app.services.project_service import ProjectService
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.services.workspace_service import WorkspaceService

# Swagger Bearer authentication scheme
security_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Dependency to retrieve and validate the authenticated user from JWT Bearer token."""
    token = credentials.credentials
    try:
        payload = decode_token(token)
        token_type = payload.get("type")
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type. Access token expected.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = int(payload.get("sub", 0))
    except (jwt.PyJWTError, ValueError) as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account.",
        )
    return user


async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Dependency ensuring current authenticated user has ADMIN role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have sufficient privileges (ADMIN required).",
        )
    return current_user


# Service provider dependencies
def get_auth_service(session: Annotated[AsyncSession, Depends(get_db)]) -> AuthService:
    return AuthService(session)


def get_user_service(session: Annotated[AsyncSession, Depends(get_db)]) -> UserService:
    return UserService(session)


def get_workspace_service(session: Annotated[AsyncSession, Depends(get_db)]) -> WorkspaceService:
    return WorkspaceService(session)


def get_project_service(session: Annotated[AsyncSession, Depends(get_db)]) -> ProjectService:
    return ProjectService(session)


def get_task_service(session: Annotated[AsyncSession, Depends(get_db)]) -> TaskService:
    return TaskService(session)


def get_label_service(session: Annotated[AsyncSession, Depends(get_db)]) -> LabelService:
    return LabelService(session)


def get_comment_service(session: Annotated[AsyncSession, Depends(get_db)]) -> CommentService:
    return CommentService(session)


class TaskFilterParams:
    """Query parameter dependency for task listing with filtering and pagination."""

    def __init__(
        self,
        status: Annotated[TaskStatus | None, Query(description="Filter by task status")] = None,
        priority: Annotated[TaskPriority | None, Query(description="Filter by priority")] = None,
        assignee_id: Annotated[int | None, Query(description="Filter by assigned user ID")] = None,
        page: Annotated[int, Query(ge=1, description="Page number starting at 1")] = 1,
        limit: Annotated[int, Query(ge=1, le=100, description="Items per page (max 100)")] = 20,
    ):
        self.status = status
        self.priority = priority
        self.assignee_id = assignee_id
        self.page = page
        self.limit = limit
