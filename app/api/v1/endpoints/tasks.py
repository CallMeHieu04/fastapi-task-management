from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Path, status

from app.api.deps import (
    get_comment_service,
    get_current_user,
    get_task_service,
)
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentResponse
from app.schemas.task import TaskResponse, TaskUpdate
from app.services.comment_service import CommentService
from app.services.task_service import TaskService

router = APIRouter()


@router.get(
    "/{id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Get task details by ID",
)
async def get_task(
    id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    """Retrieve full task information including assigned labels and comments count."""
    return await task_service.get_task(task_id=id, current_user=current_user)


@router.patch(
    "/{id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Update task details or reassign",
)
async def update_task(
    id: Annotated[int, Path(ge=1)],
    task_in: TaskUpdate,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    """Update title, description, status, priority, due date, or assignee."""
    return await task_service.update_task(
        task_id=id,
        current_user=current_user,
        task_in=task_in,
        background_tasks=background_tasks,
    )


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete task",
)
async def delete_task(
    id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> None:
    """Permanently delete a task."""
    await task_service.delete_task(task_id=id, current_user=current_user)


# Label management on task
@router.post(
    "/{id}/labels/{label_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Attach label to task",
)
async def attach_label_to_task(
    id: Annotated[int, Path(ge=1)],
    label_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    """Attach an existing project label to the specified task."""
    return await task_service.add_label_to_task(task_id=id, label_id=label_id, current_user=current_user)


@router.delete(
    "/{id}/labels/{label_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Detach label from task",
)
async def detach_label_from_task(
    id: Annotated[int, Path(ge=1)],
    label_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    """Detach a label from the specified task."""
    return await task_service.remove_label_from_task(task_id=id, label_id=label_id, current_user=current_user)


# Comment management on task
@router.get(
    "/{id}/comments",
    response_model=list[CommentResponse],
    status_code=status.HTTP_200_OK,
    summary="List comments on task",
)
async def list_task_comments(
    id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    comment_service: Annotated[CommentService, Depends(get_comment_service)],
) -> list[CommentResponse]:
    """Retrieve all comments on the specified task."""
    return await comment_service.list_comments(task_id=id, current_user=current_user)


@router.post(
    "/{id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add comment to task",
)
async def add_task_comment(
    id: Annotated[int, Path(ge=1)],
    comment_in: CommentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    comment_service: Annotated[CommentService, Depends(get_comment_service)],
) -> CommentResponse:
    """Add a new comment on the specified task."""
    return await comment_service.add_comment(task_id=id, current_user=current_user, comment_in=comment_in)
