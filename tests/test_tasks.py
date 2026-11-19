import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskPriority, TaskStatus, UserRole
from app.models.task import Task
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.base import BaseRepository


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_base_repository_pattern(db_session: AsyncSession):
    """Test generic BaseRepository[Task] CRUD and pagination functionality with Unit of Work flush."""
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


async def get_auth_headers(client: AsyncClient, email: str = "task_author@example.com") -> dict[str, str]:
    """Helper creating user and returning Bearer authorization headers."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Task Author", "password": "Password123!"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_unauthenticated_task_routes_return_401(client: AsyncClient):
    """Calling task routes without authentication returns 401."""
    res_get = await client.get("/api/v1/tasks")
    assert res_get.status_code == 401
    assert res_get.headers.get("www-authenticate") == "Bearer"

    res_post = await client.post("/api/v1/tasks", json={"title": "No Auth Task"})
    assert res_post.status_code == 401

    res_del = await client.delete("/api/v1/tasks/1")
    assert res_del.status_code == 401


@pytest.mark.asyncio
async def test_create_and_get_task(client: AsyncClient):
    headers = await get_auth_headers(client, "create_get@example.com")
    payload = {
        "title": "Design Database Schema",
        "description": "Prepare ERD for workspaces and projects.",
        "priority": "HIGH",
    }
    create_res = await client.post("/api/v1/tasks", json=payload, headers=headers)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["id"] > 0
    assert created["title"] == payload["title"]
    assert created["status"] == "TODO"

    get_res = await client.get(f"/api/v1/tasks/{created['id']}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["title"] == payload["title"]


@pytest.mark.asyncio
async def test_create_task_validation_rejects_blank_title(client: AsyncClient):
    """Creating a task with whitespace or empty title must return 422."""
    headers = await get_auth_headers(client, "blank_title@example.com")
    blank_res = await client.post("/api/v1/tasks", json={"title": "    "}, headers=headers)
    assert blank_res.status_code == 422

    empty_res = await client.post("/api/v1/tasks", json={"title": ""}, headers=headers)
    assert empty_res.status_code == 422


@pytest.mark.asyncio
async def test_task_not_found_returns_404(client: AsyncClient):
    """Accessing, updating, or deleting a non-existent task returns 404 Not Found."""
    headers = await get_auth_headers(client, "not_found@example.com")
    non_existent_id = 999999
    get_res = await client.get(f"/api/v1/tasks/{non_existent_id}", headers=headers)
    assert get_res.status_code == 404

    patch_res = await client.patch(f"/api/v1/tasks/{non_existent_id}", json={"title": "New Title"}, headers=headers)
    assert patch_res.status_code == 404

    del_res = await client.delete(f"/api/v1/tasks/{non_existent_id}", headers=headers)
    assert del_res.status_code == 404


@pytest.mark.asyncio
async def test_list_tasks_pagination_and_filter(client: AsyncClient):
    headers = await get_auth_headers(client, "list_filter@example.com")
    # Seed 3 tasks
    for i in range(1, 4):
        create_res = await client.post(
            "/api/v1/tasks",
            json={
                "title": f"Task {i}",
                "priority": "HIGH" if i == 1 else "LOW",
            },
            headers=headers,
        )
        task_id = create_res.json()["id"]
        if i == 1:
            await client.patch(f"/api/v1/tasks/{task_id}", json={"status": "DONE"}, headers=headers)

    # Test pagination
    list_res = await client.get("/api/v1/tasks?page=1&limit=2", headers=headers)
    assert list_res.status_code == 200
    data = list_res.json()
    assert len(data["items"]) == 2
    assert data["meta"]["total"] == 3
    assert data["meta"]["page"] == 1
    assert data["meta"]["page_size"] == 2

    # Test filtering by status
    filter_res = await client.get("/api/v1/tasks?status=DONE", headers=headers)
    assert filter_res.status_code == 200
    items = filter_res.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "DONE"


@pytest.mark.asyncio
async def test_patch_task_validation(client: AsyncClient):
    headers = await get_auth_headers(client, "patch_val@example.com")
    create_res = await client.post("/api/v1/tasks", json={"title": "Patch Target"}, headers=headers)
    task_id = create_res.json()["id"]

    # Valid patch
    patch_res = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "IN_PROGRESS", "priority": "URGENT"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "IN_PROGRESS"

    # Explicit null title -> 422
    null_patch = await client.patch(f"/api/v1/tasks/{task_id}", json={"title": None}, headers=headers)
    assert null_patch.status_code == 422

    # Whitespace title -> 422
    blank_patch = await client.patch(f"/api/v1/tasks/{task_id}", json={"title": "   "}, headers=headers)
    assert blank_patch.status_code == 422


@pytest.mark.asyncio
async def test_delete_task(client: AsyncClient):
    headers = await get_auth_headers(client, "delete_target@example.com")
    create_res = await client.post("/api/v1/tasks", json={"title": "Delete Target"}, headers=headers)
    task_id = create_res.json()["id"]

    del_res = await client.delete(f"/api/v1/tasks/{task_id}", headers=headers)
    assert del_res.status_code == 204

    get_res = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_sqlite_foreign_key_enforcement(db_session: AsyncSession):
    """PRAGMA foreign_keys=ON must reject inserting records pointing to non-existent FKs."""
    task_repo = BaseRepository(Task, db_session)

    # Attempt to create task pointing to non-existent project_id -> IntegrityError
    with pytest.raises(IntegrityError):
        await task_repo.create(
            title="Invalid FK Task",
            project_id=999999,
        )
    await db_session.rollback()


@pytest.mark.asyncio
async def test_workspace_owner_restrict_delete(db_session: AsyncSession):
    """Workspace.owner_id has ondelete='RESTRICT', preventing deletion of a user who owns workspaces."""
    user_repo = BaseRepository(User, db_session)
    ws_repo = BaseRepository(Workspace, db_session)

    # Create user and workspace
    user = await user_repo.create(
        email="owner_test@example.com",
        full_name="Owner User",
        hashed_password="hashed_pw_test",
        role=UserRole.MEMBER,
        is_active=True,
    )
    await ws_repo.create(name="Owned WS", owner_id=user.id)

    # Deleting user must fail due to ondelete="RESTRICT"
    with pytest.raises(IntegrityError):
        await user_repo.delete(user)
    await db_session.rollback()
