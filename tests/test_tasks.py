import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskPriority, TaskStatus
from app.models.task import Task
from app.repositories.base import BaseRepository


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_base_repository_pattern(db_session: AsyncSession):
    """Test generic BaseRepository[Task] CRUD and pagination functionality."""
    repo = BaseRepository(Task, db_session)

    # 1. Create via BaseRepository
    task = await repo.create(
        title="Base Repo Task",
        description="Testing generic repo",
        status=TaskStatus.TODO,
        priority=TaskPriority.LOW,
    )
    assert task.id > 0
    assert task.title == "Base Repo Task"

    # 2. Get by ID
    fetched = await repo.get_by_id(task.id)
    assert fetched is not None
    assert fetched.id == task.id

    # 3. Update
    updated = await repo.update(fetched, status=TaskStatus.IN_PROGRESS)
    assert updated.status == TaskStatus.IN_PROGRESS

    # 4. Get all & Pagination
    items, total = await repo.get_all(skip=0, limit=10)
    assert total >= 1
    assert len(items) >= 1

    # 5. Delete by ID
    deleted = await repo.delete_by_id(task.id)
    assert deleted is True
    assert await repo.get_by_id(task.id) is None


@pytest.mark.asyncio
async def test_create_and_get_task(client: AsyncClient):
    payload = {
        "title": "Design Database Schema",
        "description": "Prepare ERD for workspaces and projects.",
        "status": "TODO",
        "priority": "HIGH",
    }
    create_res = await client.post("/api/v1/tasks", json=payload)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["id"] > 0
    assert created["title"] == payload["title"]

    get_res = await client.get(f"/api/v1/tasks/{created['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == payload["title"]


@pytest.mark.asyncio
async def test_list_tasks_pagination_and_filter(client: AsyncClient):
    # Seed 3 tasks
    for i in range(1, 4):
        await client.post(
            "/api/v1/tasks",
            json={
                "title": f"Task {i}",
                "status": "DONE" if i == 1 else "TODO",
                "priority": "HIGH" if i == 1 else "LOW",
            },
        )

    # Test pagination
    list_res = await client.get("/api/v1/tasks?page=1&limit=2")
    assert list_res.status_code == 200
    data = list_res.json()
    assert len(data["items"]) == 2
    assert data["meta"]["total"] == 3
    assert data["meta"]["page"] == 1
    assert data["meta"]["page_size"] == 2

    # Test filtering by status
    filter_res = await client.get("/api/v1/tasks?status=DONE")
    assert filter_res.status_code == 200
    items = filter_res.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "DONE"


@pytest.mark.asyncio
async def test_patch_task_validation(client: AsyncClient):
    create_res = await client.post("/api/v1/tasks", json={"title": "Patch Target"})
    task_id = create_res.json()["id"]

    # Valid patch
    patch_res = await client.patch(f"/api/v1/tasks/{task_id}", json={"status": "IN_PROGRESS", "priority": "URGENT"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "IN_PROGRESS"

    # Explicit null title -> 422
    null_patch = await client.patch(f"/api/v1/tasks/{task_id}", json={"title": None})
    assert null_patch.status_code == 422

    # Whitespace title -> 422
    blank_patch = await client.patch(f"/api/v1/tasks/{task_id}", json={"title": "   "})
    assert blank_patch.status_code == 422


@pytest.mark.asyncio
async def test_delete_task(client: AsyncClient):
    create_res = await client.post("/api/v1/tasks", json={"title": "Delete Target"})
    task_id = create_res.json()["id"]

    del_res = await client.delete(f"/api/v1/tasks/{task_id}")
    assert del_res.status_code == 204

    get_res = await client.get(f"/api/v1/tasks/{task_id}")
    assert get_res.status_code == 404
