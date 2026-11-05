from app.core.constants import (
    MSG_COMMENT_NOT_FOUND,
    MSG_DELETE_OWN_COMMENT_ONLY,
    MSG_TASK_NOT_FOUND,
)
from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.enums import UserRole, WorkspaceMemberRole
from app.models.user import User
from app.repositories.comment_repository import CommentRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.comment import CommentCreate, CommentResponse
from app.services.workspace_service import WorkspaceService


class CommentService:
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

    async def add_comment(self, task_id: int, current_user: User, comment_in: CommentCreate) -> CommentResponse:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))
        project = await self.project_repo.get_by_id(task.project_id)
        if project:
            await self.workspace_service.check_workspace_access(
                project.workspace_id, current_user, required_role=WorkspaceMemberRole.EDITOR
            )
        comment = await self.comment_repo.create(task_id=task_id, author_id=current_user.id, comment_in=comment_in)
        return CommentResponse(
            id=comment.id,
            task_id=comment.task_id,
            author_id=comment.author_id,
            author_name=current_user.full_name,
            content=comment.content,
            created_at=comment.created_at,
        )

    async def list_comments(self, task_id: int, current_user: User) -> list[CommentResponse]:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundException(MSG_TASK_NOT_FOUND.format(id=task_id))
        project = await self.project_repo.get_by_id(task.project_id)
        if project:
            await self.workspace_service.check_workspace_access(project.workspace_id, current_user)
        comments = await self.comment_repo.list_by_task(task_id)
        return [
            CommentResponse(
                id=c.id,
                task_id=c.task_id,
                author_id=c.author_id,
                author_name=c.author.full_name if c.author else None,
                content=c.content,
                created_at=c.created_at,
            )
            for c in comments
        ]

    async def delete_comment(self, comment_id: int, current_user: User) -> None:
        comment = await self.comment_repo.get_by_id(comment_id)
        if not comment:
            raise NotFoundException(MSG_COMMENT_NOT_FOUND.format(id=comment_id))
        # Author or Admin can delete comment
        if comment.author_id != current_user.id and current_user.role != UserRole.ADMIN:
            raise ForbiddenException(MSG_DELETE_OWN_COMMENT_ONLY)
        await self.comment_repo.delete(comment)
