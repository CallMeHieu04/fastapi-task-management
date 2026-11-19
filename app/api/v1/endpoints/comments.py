from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.deps import CurrentUser, PaginationParams, get_comment_service
from app.schemas.comment import CommentCreate, CommentResponse, CommentUpdate
from app.schemas.common import PaginatedResponse
from app.services.comment_service import CommentService

router = APIRouter()


@router.post(
    "/tasks/{id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add comment to task",
    description="Add a comment to the task (Workspace members only).",
    responses={
        400: {"description": "Project archived or invalid task"},
        403: {"description": "Access denied (not a workspace member)"},
        404: {"description": "Task not found"},
    },
)
async def add_task_comment(
    id: Annotated[int, Path(ge=1, description="Task ID")],
    comment_in: CommentCreate,
    current_user: CurrentUser,
    comment_service: Annotated[CommentService, Depends(get_comment_service)],
) -> CommentResponse:
    """Add a new comment to a task."""
    return await comment_service.create_comment(task_id=id, current_user=current_user, comment_in=comment_in)


@router.get(
    "/tasks/{id}/comments",
    response_model=PaginatedResponse[CommentResponse],
    status_code=status.HTTP_200_OK,
    summary="List task comments",
    description="Retrieve paginated comments for a task ordered chronologically (Workspace members only).",
    responses={
        403: {"description": "Access denied (not a workspace member)"},
        404: {"description": "Task not found"},
    },
)
async def list_task_comments(
    id: Annotated[int, Path(ge=1, description="Task ID")],
    pagination: Annotated[PaginationParams, Depends()],
    current_user: CurrentUser,
    comment_service: Annotated[CommentService, Depends(get_comment_service)],
) -> PaginatedResponse[CommentResponse]:
    """Retrieve paginated comments for a task."""
    return await comment_service.list_comments(
        task_id=id,
        current_user=current_user,
        page=pagination.page,
        limit=pagination.limit,
    )


@router.patch(
    "/comments/{id}",
    response_model=CommentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update comment",
    description="Update comment content (Author only).",
    responses={
        400: {"description": "Project archived"},
        403: {"description": "Permission denied (You can only edit your own comment)"},
        404: {"description": "Comment not found"},
        422: {"description": "Validation error"},
    },
)
async def update_comment(
    id: Annotated[int, Path(ge=1, description="Comment ID")],
    comment_in: CommentUpdate,
    current_user: CurrentUser,
    comment_service: Annotated[CommentService, Depends(get_comment_service)],
) -> CommentResponse:
    """Partially update a comment's content."""
    return await comment_service.update_comment(comment_id=id, current_user=current_user, comment_in=comment_in)


@router.delete(
    "/comments/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete comment",
    description="Delete a comment (Comment author, Workspace OWNER, or system ADMIN).",
    responses={
        403: {"description": "Permission denied (You can only delete your own comments)"},
        404: {"description": "Comment not found"},
    },
)
async def delete_comment(
    id: Annotated[int, Path(ge=1, description="Comment ID")],
    current_user: CurrentUser,
    comment_service: Annotated[CommentService, Depends(get_comment_service)],
) -> None:
    """Delete a comment by ID."""
    await comment_service.delete_comment(comment_id=id, current_user=current_user)
