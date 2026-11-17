from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.deps import CurrentUser, get_comment_service
from app.schemas.comment import CommentResponse, CommentUpdate
from app.services.comment_service import CommentService

router = APIRouter()


@router.patch(
    "/{id}",
    response_model=CommentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update comment",
    description="Update comment content (Author only).",
    responses={
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
    "/{id}",
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
