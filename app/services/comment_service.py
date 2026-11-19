import math

from app.core.constants import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MSG_COMMENT_NOT_FOUND,
    MSG_DELETE_OWN_COMMENT_ONLY,
    MSG_EDIT_OWN_COMMENT_ONLY,
    MSG_PROJECT_ARCHIVED,
    MSG_PROJECT_NOT_FOUND,
    MSG_TASK_NOT_FOUND,
)
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.enums import ProjectStatus, UserRole, WorkspaceMemberRole
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.repositories.comment_repository import CommentRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.comment import CommentCreate, CommentResponse, CommentUpdate
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.services.workspace_service import WorkspaceService


class CommentService:
    """Service handling task comments, resource ownership validation, and workspace RBAC."""

    def __init__(
        self,
        comment_repo: CommentRepository,
        task_repo: TaskRepository,
        project_repo: ProjectRepository,
        workspace_service: WorkspaceService,
    ) -> None:
        self.comment_repo = comment_repo
        self.task_repo = task_repo
        self.project_repo = project_repo
        self.workspace_service = workspace_service

    async def _verify_task_workspace_access(
        self,
        task_id: int,
        current_user: User,
        required_role: WorkspaceMemberRole | None = None,
        for_write: bool = False,
    ) -> tuple[Task, Project]:
        """Helper to verify task exists and current user has workspace access to its project."""
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))

        if task.project_id is None:
            raise BadRequestException("Task does not belong to a project.")

        project = await self.project_repo.get_by_id(task.project_id)
        if not project:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=task.project_id))

        try:
            await self.workspace_service.check_workspace_access(
                workspace_id=project.workspace_id,
                current_user=current_user,
                required_role=required_role,
            )
        except NotFoundException:
            raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=task.project_id)) from None

        if for_write and project.status == ProjectStatus.ARCHIVED:
            raise BadRequestException(MSG_PROJECT_ARCHIVED)

        return task, project

    async def create_comment(
        self,
        task_id: int,
        current_user: User,
        comment_in: CommentCreate,
    ) -> CommentResponse:
        """Add a comment to a task (Workspace members only)."""
        await self._verify_task_workspace_access(task_id=task_id, current_user=current_user, for_write=True)

        comment = await self.comment_repo.create(
            task_id=task_id,
            author_id=current_user.id,
            content=comment_in.content,
        )
        comment.author = current_user
        return CommentResponse.model_validate(comment)

    async def list_comments(
        self,
        task_id: int,
        current_user: User,
        page: int = DEFAULT_PAGE,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> PaginatedResponse[CommentResponse]:
        """List paginated comments for a task in chronological order (Workspace members only)."""
        await self._verify_task_workspace_access(task_id=task_id, current_user=current_user)

        offset = (page - 1) * limit
        comments, total = await self.comment_repo.list_by_task(task_id=task_id, offset=offset, limit=limit)
        total_pages = math.ceil(total / limit) if total > 0 else 0

        items = [CommentResponse.model_validate(c) for c in comments]
        return PaginatedResponse[CommentResponse](
            items=items,
            meta=PaginationMeta(
                page=page,
                page_size=limit,
                total=total,
                total_pages=total_pages,
            ),
        )

    async def update_comment(
        self,
        comment_id: int,
        current_user: User,
        comment_in: CommentUpdate,
    ) -> CommentResponse:
        """Update comment content (Author only)."""
        comment = await self.comment_repo.get_by_id(comment_id)
        if not comment:
            raise NotFoundException(MSG_COMMENT_NOT_FOUND.format(id=comment_id))

        # Check membership and project status first
        await self._verify_task_workspace_access(
            task_id=comment.task_id,
            current_user=current_user,
            for_write=True,
        )

        # Strictly author only: ADMIN cannot modify other authors' comment content
        if comment.author_id != current_user.id:
            raise ForbiddenException(MSG_EDIT_OWN_COMMENT_ONLY)

        update_data = comment_in.model_dump(exclude_unset=True)
        updated = await self.comment_repo.update(comment, **update_data)
        return CommentResponse.model_validate(updated)

    async def delete_comment(
        self,
        comment_id: int,
        current_user: User,
    ) -> None:
        """Delete a comment (Author, Workspace OWNER, or system ADMIN)."""
        comment = await self.comment_repo.get_by_id(comment_id)
        if not comment:
            raise NotFoundException(MSG_COMMENT_NOT_FOUND.format(id=comment_id))

        if current_user.role != UserRole.ADMIN:
            # Check membership in workspace first
            _, project = await self._verify_task_workspace_access(
                task_id=comment.task_id,
                current_user=current_user,
            )

            is_author = comment.author_id == current_user.id
            is_workspace_owner = await self.workspace_service.is_workspace_owner(
                workspace_id=project.workspace_id,
                user_id=current_user.id,
            )

            if not (is_author or is_workspace_owner):
                raise ForbiddenException(MSG_DELETE_OWN_COMMENT_ONLY)

        await self.comment_repo.delete(comment)
