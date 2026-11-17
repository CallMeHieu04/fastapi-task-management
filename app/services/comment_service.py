from app.core.constants import (
    MSG_COMMENT_NOT_FOUND,
    MSG_DELETE_OWN_COMMENT_ONLY,
    MSG_PROJECT_NOT_FOUND,
    MSG_TASK_NOT_FOUND,
)
from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.enums import UserRole, WorkspaceMemberRole
from app.models.user import User
from app.repositories.comment_repository import CommentRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.comment import CommentCreate, CommentResponse, CommentUpdate
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
    ) -> int | None:
        """Helper to verify workspace access for a task's parent project."""
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))

        if task.project_id is not None:
            project = await self.project_repo.get_by_id(task.project_id)
            if not project:
                raise NotFoundException(MSG_PROJECT_NOT_FOUND.format(id=task.project_id))
            await self.workspace_service.check_workspace_access(
                workspace_id=project.workspace_id,
                current_user=current_user,
                required_role=required_role,
            )
            return project.workspace_id
        return None

    async def create_comment(
        self,
        task_id: int,
        current_user: User,
        comment_in: CommentCreate,
    ) -> CommentResponse:
        """Add a comment to a task (Workspace members only)."""
        await self._verify_task_workspace_access(task_id=task_id, current_user=current_user)

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
    ) -> list[CommentResponse]:
        """List comments for a task in chronological order (Workspace members only)."""
        await self._verify_task_workspace_access(task_id=task_id, current_user=current_user)

        comments = await self.comment_repo.list_by_task(task_id=task_id)
        return [CommentResponse.model_validate(c) for c in comments]

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

        # Check resource ownership
        if comment.author_id != current_user.id and current_user.role != UserRole.ADMIN:
            raise ForbiddenException("You can only modify your own comments.")

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

        # If user is the author or admin, permission granted
        is_author = comment.author_id == current_user.id
        is_admin = current_user.role == UserRole.ADMIN

        is_workspace_owner = False
        task = await self.task_repo.get_by_id(comment.task_id)
        if task and task.project_id:
            project = await self.project_repo.get_by_id(task.project_id)
            if project:
                try:
                    await self.workspace_service.check_workspace_access(
                        workspace_id=project.workspace_id,
                        current_user=current_user,
                        required_role=WorkspaceMemberRole.OWNER,
                    )
                    is_workspace_owner = True
                except Exception:
                    is_workspace_owner = False

        if not (is_author or is_admin or is_workspace_owner):
            raise ForbiddenException(MSG_DELETE_OWN_COMMENT_ONLY)

        await self.comment_repo.delete(comment)
