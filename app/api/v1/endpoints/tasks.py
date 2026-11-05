from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.api.deps import TaskFilterParams, get_task_service
from app.schemas.common import PaginatedResponse
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from app.services.task_service import TaskService

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    summary="List all tasks",
    description="Retrieve paginated tasks with optional status, priority, and keyword filtering.",
)
@router.get(
    "/",
    response_model=PaginatedResponse[TaskResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def list_tasks(
    filters: Annotated[TaskFilterParams, Depends()],
    service: Annotated[TaskService, Depends(get_task_service)],
) -> PaginatedResponse[TaskResponse]:
    return await service.list_tasks(
        status=filters.status,
        priority=filters.priority,
        search=filters.search,
        page=filters.page,
        page_size=filters.limit,
    )


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
    description="Create a task with validated title, optional description, status, and priority.",
)
@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_task(
    task_in: TaskCreate,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    return await service.create_task(task_in=task_in)


@router.get(
    "/{id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Get task details",
    description="Retrieve details of a single task by its integer identifier.",
)
async def get_task(
    id: Annotated[int, Path(ge=1, description="The ID of the task")],
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    return await service.get_task(task_id=id)


@router.patch(
    "/{id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update a task",
    description="Update task fields. Explicit null on required fields is rejected with 422.",
)
async def update_task(
    id: Annotated[int, Path(ge=1, description="The ID of the task")],
    task_in: TaskUpdate,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    return await service.update_task(task_id=id, task_in=task_in)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
    description="Delete a task by ID. Returns 204 No Content.",
)
async def delete_task(
    id: Annotated[int, Path(ge=1, description="The ID of the task")],
    service: Annotated[TaskService, Depends(get_task_service)],
) -> None:
    await service.delete_task(task_id=id)
