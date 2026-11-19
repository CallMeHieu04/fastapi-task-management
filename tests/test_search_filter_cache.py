from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core.cache import InMemoryFallbackCache, cache_service
from tests.conftest import create_user_and_token


@pytest.mark.asyncio
async def test_in_memory_fallback_cache():
    """Unit test for InMemoryFallbackCache operations: get, set, delete, delete_pattern, expiry."""
    cache = InMemoryFallbackCache()

    # Set and Get
    await cache.set("test:1", "val1", ex=60)
    assert await cache.get("test:1") == "val1"

    # Delete
    await cache.delete("test:1")
    assert await cache.get("test:1") is None

    # Delete pattern
    await cache.set("pattern:a:1", "alpha", ex=60)
    await cache.set("pattern:a:2", "beta", ex=60)
    await cache.set("pattern:b:1", "gamma", ex=60)

    await cache.delete_pattern("pattern:a:*")
    assert await cache.get("pattern:a:1") is None
    assert await cache.get("pattern:a:2") is None
    assert await cache.get("pattern:b:1") == "gamma"

    # Expiry test
    await cache.set("expiring", "now", ex=-1)
    assert await cache.get("expiring") is None


@pytest.mark.asyncio
async def test_cache_service_json_and_fallback():
    """Unit test for CacheService JSON serialization and graceful degradation."""
    await cache_service.set_json("json:task:1", {"id": 1, "title": "Cached Task"}, ttl=60)
    data = await cache_service.get_json("json:task:1")
    assert data is not None
    assert data["id"] == 1
    assert data["title"] == "Cached Task"

    await cache_service.delete("json:task:1")
    assert await cache_service.get_json("json:task:1") is None


@pytest.mark.asyncio
async def test_task_search_and_filtering(client: AsyncClient):
    """Test searching tasks by keyword, filtering by status, priority, assignee, and label."""
    token, user_id = await create_user_and_token(client, "s_filter@example.com", "Search User")
    token_dev, dev_id = await create_user_and_token(client, "s_dev@example.com", "Dev User")
    headers = {"Authorization": f"Bearer {token}"}

    # Setup Workspace & Project
    ws = (await client.post("/api/v1/workspaces", json={"name": "Filter Workspace"}, headers=headers)).json()
    ws_id = ws["id"]

    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "s_dev@example.com", "role": "EDITOR"},
        headers=headers,
    )

    proj = (
        await client.post(f"/api/v1/workspaces/{ws_id}/projects", json={"name": "Filter Proj"}, headers=headers)
    ).json()
    proj_id = proj["id"]

    # Create Label
    lbl = (
        await client.post(
            f"/api/v1/projects/{proj_id}/labels",
            json={"name": "Backend", "color": "#10B981"},
            headers=headers,
        )
    ).json()
    lbl_id = lbl["id"]

    # Create 3 Tasks:
    # Task 1: "Implement Redis Cache", TODO, HIGH, assigned to dev, with label
    t1_res = await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        json={
            "title": "Implement Redis Cache",
            "description": "Add caching layer for performance",
            "priority": "HIGH",
            "assignee_id": dev_id,
        },
        headers=headers,
    )
    t1 = t1_res.json()
    await client.post(f"/api/v1/tasks/{t1['id']}/labels/{lbl_id}", headers=headers)

    # Task 2: "Write Documentation", IN_PROGRESS, LOW, assigned to user
    t2_res = await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        json={
            "title": "Write Documentation",
            "description": "API swagger and README updates",
            "priority": "LOW",
            "assignee_id": user_id,
        },
        headers=headers,
    )
    t2 = t2_res.json()
    await client.patch(f"/api/v1/tasks/{t2['id']}", json={"status": "IN_PROGRESS"}, headers=headers)

    # Task 3: "Fix Frontend Bug", TODO, URGENT, no assignee, future due date
    future_date = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    t3_res = await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        json={
            "title": "Fix Frontend Bug",
            "description": "Button alignment issue on navbar",
            "priority": "URGENT",
            "due_date": future_date,
        },
        headers=headers,
    )
    t3 = t3_res.json()

    # 1. Search keyword "Redis" -> matches Task 1
    res_search = await client.get(f"/api/v1/projects/{proj_id}/tasks?search=Redis", headers=headers)
    assert res_search.status_code == 200
    items = res_search.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == t1["id"]

    # 2. Filter by status=IN_PROGRESS -> matches Task 2
    res_status = await client.get(f"/api/v1/projects/{proj_id}/tasks?status=IN_PROGRESS", headers=headers)
    assert res_status.status_code == 200
    items = res_status.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == t2["id"]

    # 3. Filter by priority=URGENT -> matches Task 3
    res_prio = await client.get(f"/api/v1/projects/{proj_id}/tasks?priority=URGENT", headers=headers)
    assert res_prio.status_code == 200
    items = res_prio.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == t3["id"]

    # 4. Filter by assignee_id=dev_id -> matches Task 1
    res_assignee = await client.get(f"/api/v1/projects/{proj_id}/tasks?assignee_id={dev_id}", headers=headers)
    assert res_assignee.status_code == 200
    items = res_assignee.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == t1["id"]

    # 5. Filter by label_id=lbl_id -> matches Task 1
    res_label = await client.get(f"/api/v1/projects/{proj_id}/tasks?label_id={lbl_id}", headers=headers)
    assert res_label.status_code == 200
    items = res_label.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == t1["id"]

    # 6. Combined filter: status=TODO & priority=HIGH -> matches Task 1
    res_comb = await client.get(f"/api/v1/projects/{proj_id}/tasks?status=TODO&priority=HIGH", headers=headers)
    assert res_comb.status_code == 200
    items = res_comb.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == t1["id"]


@pytest.mark.asyncio
async def test_task_sorting_and_pagination(client: AsyncClient):
    """Test task sorting (asc/desc) and pagination meta envelope."""
    token, _ = await create_user_and_token(client, "s_sort@example.com", "Sort User")
    headers = {"Authorization": f"Bearer {token}"}

    ws = (await client.post("/api/v1/workspaces", json={"name": "Sort WS"}, headers=headers)).json()
    proj = (
        await client.post(f"/api/v1/workspaces/{ws['id']}/projects", json={"name": "Sort Proj"}, headers=headers)
    ).json()
    proj_id = proj["id"]

    # Create 4 tasks with alphabetical titles
    titles = ["Alpha Task", "Beta Task", "Gamma Task", "Delta Task"]
    for title in titles:
        res = await client.post(f"/api/v1/projects/{proj_id}/tasks", json={"title": title}, headers=headers)
        assert res.status_code == 201

    # Sort by title ASC
    res_asc = await client.get(f"/api/v1/projects/{proj_id}/tasks?sort_by=title&order=asc", headers=headers)
    assert res_asc.status_code == 200
    asc_titles = [t["title"] for t in res_asc.json()["items"]]
    assert asc_titles == ["Alpha Task", "Beta Task", "Delta Task", "Gamma Task"]

    # Sort by title DESC
    res_desc = await client.get(f"/api/v1/projects/{proj_id}/tasks?sort_by=title&order=desc", headers=headers)
    assert res_desc.status_code == 200
    desc_titles = [t["title"] for t in res_desc.json()["items"]]
    assert desc_titles == ["Gamma Task", "Delta Task", "Beta Task", "Alpha Task"]

    # Pagination: page 1 with limit 2
    p1 = await client.get(f"/api/v1/projects/{proj_id}/tasks?page=1&limit=2&sort_by=title&order=asc", headers=headers)
    assert p1.status_code == 200
    p1_data = p1.json()
    assert len(p1_data["items"]) == 2
    assert p1_data["meta"]["total"] == 4
    assert p1_data["meta"]["page"] == 1
    assert p1_data["meta"]["page_size"] == 2
    assert p1_data["meta"]["total_pages"] == 2
    assert [t["title"] for t in p1_data["items"]] == ["Alpha Task", "Beta Task"]

    # Pagination: page 2 with limit 2
    p2 = await client.get(f"/api/v1/projects/{proj_id}/tasks?page=2&limit=2&sort_by=title&order=asc", headers=headers)
    assert p2.status_code == 200
    p2_data = p2.json()
    assert len(p2_data["items"]) == 2
    assert [t["title"] for t in p2_data["items"]] == ["Delta Task", "Gamma Task"]


@pytest.mark.asyncio
async def test_project_search_and_filtering(client: AsyncClient):
    """Test searching and filtering projects within a workspace."""
    token, _ = await create_user_and_token(client, "s_proj@example.com", "Proj Search User")
    headers = {"Authorization": f"Bearer {token}"}

    ws = (await client.post("/api/v1/workspaces", json={"name": "Proj Search WS"}, headers=headers)).json()
    ws_id = ws["id"]

    # Create 3 projects
    await client.post(f"/api/v1/workspaces/{ws_id}/projects", json={"name": "Frontend Web App"}, headers=headers)
    p2 = (
        await client.post(f"/api/v1/workspaces/{ws_id}/projects", json={"name": "Backend REST API"}, headers=headers)
    ).json()
    p3 = (
        await client.post(f"/api/v1/workspaces/{ws_id}/projects", json={"name": "Mobile Flutter App"}, headers=headers)
    ).json()

    # Archive p3
    await client.patch(f"/api/v1/projects/{p3['id']}", json={"status": "ARCHIVED"}, headers=headers)

    # Search "Backend"
    res_q = await client.get(f"/api/v1/workspaces/{ws_id}/projects?search=Backend", headers=headers)
    assert res_q.status_code == 200
    items = res_q.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == p2["id"]

    # Filter status=ARCHIVED
    res_arch = await client.get(f"/api/v1/workspaces/{ws_id}/projects?status=ARCHIVED", headers=headers)
    assert res_arch.status_code == 200
    items = res_arch.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == p3["id"]

    # Filter status=ACTIVE
    res_act = await client.get(f"/api/v1/workspaces/{ws_id}/projects?status=ACTIVE", headers=headers)
    assert res_act.status_code == 200
    assert len(res_act.json()["items"]) == 2


@pytest.mark.asyncio
async def test_workspace_search(client: AsyncClient):
    """Test searching workspaces by name keyword."""
    token, _ = await create_user_and_token(client, "s_ws@example.com", "WS Search User")
    headers = {"Authorization": f"Bearer {token}"}

    await client.post("/api/v1/workspaces", json={"name": "Engineering Team"}, headers=headers)
    await client.post("/api/v1/workspaces", json={"name": "Marketing Agency"}, headers=headers)

    res = await client.get("/api/v1/workspaces?search=Engineering", headers=headers)
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Engineering Team"


@pytest.mark.asyncio
async def test_task_cache_and_invalidation(client: AsyncClient):
    """Test that task details are cached and invalidated upon update and deletion."""
    token, _ = await create_user_and_token(client, "cache_task@example.com", "Cache User")
    headers = {"Authorization": f"Bearer {token}"}

    ws = (await client.post("/api/v1/workspaces", json={"name": "Cache WS"}, headers=headers)).json()
    proj = (
        await client.post(f"/api/v1/workspaces/{ws['id']}/projects", json={"name": "Cache Proj"}, headers=headers)
    ).json()
    t_res = await client.post(f"/api/v1/projects/{proj['id']}/tasks", json={"title": "Original Title"}, headers=headers)
    task_id = t_res.json()["id"]

    # 1. Fetch task (populates cache)
    get1 = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    assert get1.status_code == 200
    assert get1.json()["title"] == "Original Title"

    # Verify task was placed in cache
    cached_val = await cache_service.get_json(f"tasks:detail:{task_id}")
    assert cached_val is not None
    assert cached_val["title"] == "Original Title"

    # 2. Update task (should invalidate cache)
    patch_res = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "Updated Cache Title"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Updated Cache Title"

    # Verify cache key was purged
    assert await cache_service.get_json(f"tasks:detail:{task_id}") is None

    # 3. Fetch again (re-populates cache with updated title)
    get2 = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    assert get2.status_code == 200
    assert get2.json()["title"] == "Updated Cache Title"

    # 4. Delete task (invalidates cache)
    del_res = await client.delete(f"/api/v1/tasks/{task_id}", headers=headers)
    assert del_res.status_code == 204
    assert await cache_service.get_json(f"tasks:detail:{task_id}") is None


@pytest.mark.asyncio
async def test_process_time_middleware(client: AsyncClient):
    """Test that HTTP responses include the X-Process-Time performance header."""
    res = await client.get("/health")
    assert res.status_code == 200
    assert "x-process-time" in res.headers
    assert float(res.headers["x-process-time"]) >= 0.0
