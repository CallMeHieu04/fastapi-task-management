from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.deps import get_comment_service, get_current_user
from app.models.user import User
from app.services.comment_service import CommentService

router = APIRouter()


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete comment",
)
async def delete_comment(
    id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    comment_service: Annotated[CommentService, Depends(get_comment_service)],
) -> None:
    """Delete a comment (must be the author or system admin)."""
    await comment_service.delete_comment(comment_id=id, current_user=current_user)
