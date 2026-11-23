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


@pytest.mark.asyncio
async def test_due_date_filter_cache_isolation(client: AsyncClient):
    """Verify that different due_date_from / due_date_to filters generate distinct cache keys."""
    token, _ = await create_user_and_token(client, "due_cache@example.com", "Due Date User")
    headers = {"Authorization": f"Bearer {token}"}

    ws = (await client.post("/api/v1/workspaces", json={"name": "Due WS"}, headers=headers)).json()
    proj = (
        await client.post(f"/api/v1/workspaces/{ws['id']}/projects", json={"name": "Due Proj"}, headers=headers)
    ).json()

    # Task 1: due 2030-01-15
    await client.post(
        f"/api/v1/projects/{proj['id']}/tasks",
        json={"title": "Early Task", "due_date": "2030-01-15T00:00:00Z"},
        headers=headers,
    )
    # Task 2: due 2030-06-15
    await client.post(
        f"/api/v1/projects/{proj['id']}/tasks",
        json={"title": "Late Task", "due_date": "2030-06-15T00:00:00Z"},
        headers=headers,
    )

    # 1. Query due_date_to = 2030-02-01 (should return Early Task only)
    res1 = await client.get(
        f"/api/v1/projects/{proj['id']}/tasks?due_date_to=2030-02-01T00:00:00Z",
        headers=headers,
    )
    assert res1.status_code == 200
    items1 = res1.json()["items"]
    assert len(items1) == 1
    assert items1[0]["title"] == "Early Task"

    # 2. Query due_date_from = 2030-05-01 (should return Late Task only, not cached Early Task)
    res2 = await client.get(
        f"/api/v1/projects/{proj['id']}/tasks?due_date_from=2030-05-01T00:00:00Z",
        headers=headers,
    )
    assert res2.status_code == 200
    items2 = res2.json()["items"]
    assert len(items2) == 1
    assert items2[0]["title"] == "Late Task"


@pytest.mark.asyncio
async def test_workspace_member_removal_invalidates_task_cache(client: AsyncClient):
    """Verify that removing a member from a workspace purges task cache so the ex-member loses access."""
    token_owner, _ = await create_user_and_token(client, "ws_owner@example.com", "WS Owner")
    token_member, member_id = await create_user_and_token(client, "ws_member@example.com", "WS Member")
    owner_headers = {"Authorization": f"Bearer {token_owner}"}
    member_headers = {"Authorization": f"Bearer {token_member}"}

    ws = (await client.post("/api/v1/workspaces", json={"name": "Shared WS"}, headers=owner_headers)).json()
    ws_id = ws["id"]
    proj = (
        await client.post(f"/api/v1/workspaces/{ws_id}/projects", json={"name": "Shared Proj"}, headers=owner_headers)
    ).json()
    await client.post(
        f"/api/v1/projects/{proj['id']}/tasks", json={"title": "Confidential Task"}, headers=owner_headers
    )

    # Add member
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": member_id, "role": "VIEWER"},
        headers=owner_headers,
    )

    # Member lists tasks (populates cache)
    list1 = await client.get("/api/v1/tasks", headers=member_headers)
    assert list1.status_code == 200
    assert len(list1.json()["items"]) == 1
    assert list1.json()["items"][0]["title"] == "Confidential Task"

    # Owner removes member from workspace
    del_res = await client.delete(f"/api/v1/workspaces/{ws_id}/members/{member_id}", headers=owner_headers)
    assert del_res.status_code == 204

    # Member lists tasks again - must NOT see cached task
    list2 = await client.get("/api/v1/tasks", headers=member_headers)
    assert list2.status_code == 200
    assert len(list2.json()["items"]) == 0


@pytest.mark.asyncio
async def test_label_update_and_delete_invalidates_task_cache(client: AsyncClient):
    """Verify that updating or deleting a label purges task caches to prevent stale label data in TaskResponse."""
    token, _ = await create_user_and_token(client, "lbl_cache@example.com", "Label Cache User")
    headers = {"Authorization": f"Bearer {token}"}

    ws = (await client.post("/api/v1/workspaces", json={"name": "Lbl WS"}, headers=headers)).json()
    proj = (
        await client.post(f"/api/v1/workspaces/{ws['id']}/projects", json={"name": "Lbl Proj"}, headers=headers)
    ).json()

    lbl = (
        await client.post(
            f"/api/v1/projects/{proj['id']}/labels", json={"name": "Initial Label", "color": "#10B981"}, headers=headers
        )
    ).json()
    lbl_id = lbl["id"]

    task = (
        await client.post(f"/api/v1/projects/{proj['id']}/tasks", json={"title": "Labeled Task"}, headers=headers)
    ).json()
    task_id = task["id"]

    # Attach label
    await client.post(f"/api/v1/tasks/{task_id}/labels/{lbl_id}", headers=headers)

    # 1. Fetch task detail (populates cache)
    d1 = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    assert d1.status_code == 200
    assert len(d1.json()["labels"]) == 1
    assert d1.json()["labels"][0]["name"] == "Initial Label"

    # 2. Update label name (must invalidate tasks:* cache)
    patch_lbl = await client.patch(f"/api/v1/labels/{lbl_id}", json={"name": "Renamed Label"}, headers=headers)
    assert patch_lbl.status_code == 200

    # Task detail must return fresh label name, not cached old name
    d2 = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    assert d2.status_code == 200
    assert d2.json()["labels"][0]["name"] == "Renamed Label"

    # 3. Delete label (must invalidate tasks:* cache)
    del_lbl = await client.delete(f"/api/v1/labels/{lbl_id}", headers=headers)
    assert del_lbl.status_code == 204

    # Task detail must reflect that label is gone
    d3 = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    assert d3.status_code == 200
    assert len(d3.json()["labels"]) == 0


@pytest.mark.asyncio
async def test_priority_sorting_logical_order(client: AsyncClient):
    """Verify that sorting by priority uses logical rank (LOW < MEDIUM < HIGH < URGENT), not alphabetical."""
    token, _ = await create_user_and_token(client, "prio_sort@example.com", "Prio Sort User")
    headers = {"Authorization": f"Bearer {token}"}

    ws = (await client.post("/api/v1/workspaces", json={"name": "Prio WS"}, headers=headers)).json()
    proj = (
        await client.post(f"/api/v1/workspaces/{ws['id']}/projects", json={"name": "Prio Proj"}, headers=headers)
    ).json()
    proj_id = proj["id"]

    # Create tasks in mixed order
    await client.post(
        f"/api/v1/projects/{proj_id}/tasks", json={"title": "T_URGENT", "priority": "URGENT"}, headers=headers
    )
    await client.post(f"/api/v1/projects/{proj_id}/tasks", json={"title": "T_LOW", "priority": "LOW"}, headers=headers)
    await client.post(
        f"/api/v1/projects/{proj_id}/tasks", json={"title": "T_HIGH", "priority": "HIGH"}, headers=headers
    )
    await client.post(
        f"/api/v1/projects/{proj_id}/tasks", json={"title": "T_MEDIUM", "priority": "MEDIUM"}, headers=headers
    )

    # Sort priority ASC -> LOW, MEDIUM, HIGH, URGENT
    res_asc = await client.get(f"/api/v1/projects/{proj_id}/tasks?sort_by=priority&order=asc", headers=headers)
    assert res_asc.status_code == 200
    prios_asc = [t["priority"] for t in res_asc.json()["items"]]
    assert prios_asc == ["LOW", "MEDIUM", "HIGH", "URGENT"]

    # Sort priority DESC -> URGENT, HIGH, MEDIUM, LOW
    res_desc = await client.get(f"/api/v1/projects/{proj_id}/tasks?sort_by=priority&order=desc", headers=headers)
    assert res_desc.status_code == 200
    prios_desc = [t["priority"] for t in res_desc.json()["items"]]
    assert prios_desc == ["URGENT", "HIGH", "MEDIUM", "LOW"]


@pytest.mark.asyncio
async def test_invalid_sort_by_and_order_validation(client: AsyncClient):
    """Verify that invalid sort_by or order query parameter triggers 422 Unprocessable Entity."""
    token, _ = await create_user_and_token(client, "val_sort@example.com", "Val Sort User")
    headers = {"Authorization": f"Bearer {token}"}

    ws = (await client.post("/api/v1/workspaces", json={"name": "Val WS"}, headers=headers)).json()
    proj = (
        await client.post(f"/api/v1/workspaces/{ws['id']}/projects", json={"name": "Val Proj"}, headers=headers)
    ).json()

    # Bogus sort_by on tasks -> 422
    res_bogus_task = await client.get(f"/api/v1/projects/{proj['id']}/tasks?sort_by=bogus", headers=headers)
    assert res_bogus_task.status_code == 422

    # Bogus order on tasks -> 422
    res_bogus_order = await client.get(f"/api/v1/projects/{proj['id']}/tasks?order=random", headers=headers)
    assert res_bogus_order.status_code == 422

    # Bogus sort_by on projects -> 422
    res_bogus_proj = await client.get(f"/api/v1/workspaces/{ws['id']}/projects?sort_by=invalid_col", headers=headers)
    assert res_bogus_proj.status_code == 422
