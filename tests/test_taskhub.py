import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_and_root(client: AsyncClient):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy"}

    res = await client.get("/")
    assert res.status_code == 200
    assert res.json()["service"] == "TaskHub"


@pytest.mark.asyncio
async def test_auth_workflow(client: AsyncClient):
    # 1. Register User
    reg_payload = {
        "email": "alice@example.com",
        "full_name": "Alice Developer",
        "password": "securepassword123",
        "role": "MEMBER",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    user_data = reg_res.json()
    assert user_data["email"] == "alice@example.com"
    assert "id" in user_data

    # Duplicate registration should return 400
    dup_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert dup_res.status_code == 400

    # 2. Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "securepassword123"},
    )
    assert login_res.status_code == 200
    tokens = login_res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    access_token = tokens["access_token"]
    assert access_token.startswith("eyJ")
    refresh_token = tokens["refresh_token"]

    # 3. Refresh Token
    refresh_res = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert refresh_res.status_code == 200
    new_tokens = refresh_res.json()
    assert "access_token" in new_tokens
    new_refresh = new_tokens["refresh_token"]

    # 4. Old refresh token should now be revoked
    old_refresh_res = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert old_refresh_res.status_code == 401

    # 5. Logout with new refresh token
    logout_res = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": new_refresh}
    )
    assert logout_res.status_code == 200

    # Revoked token cannot refresh
    after_logout_res = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_refresh}
    )
    assert after_logout_res.status_code == 401


@pytest.mark.asyncio
async def test_user_profile_and_workspace_full_lifecycle(client: AsyncClient):
    # Register Alice (Owner) and Bob (Member)
    await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "full_name": "Workspace Owner", "password": "pass123456"},
    )
    owner_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "pass123456"},
    )
    owner_token = owner_login.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    await client.post(
        "/api/v1/auth/register",
        json={"email": "bob@example.com", "full_name": "Bob Member", "password": "pass123456"},
    )
    bob_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "pass123456"},
    )
    bob_token = bob_login.json()["access_token"]
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    # Test /users/me
    me_res = await client.get("/api/v1/users/me", headers=owner_headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "owner@example.com"

    # Test PATCH /users/me
    patch_me = await client.patch(
        "/api/v1/users/me", json={"full_name": "Super Owner"}, headers=owner_headers
    )
    assert patch_me.status_code == 200
    assert patch_me.json()["full_name"] == "Super Owner"

    # 1. Create Workspace
    ws_res = await client.post(
        "/api/v1/workspaces", json={"name": "Engineering Workspace"}, headers=owner_headers
    )
    assert ws_res.status_code == 201
    ws = ws_res.json()
    ws_id = ws["id"]
    assert ws["name"] == "Engineering Workspace"

    # List workspaces
    ws_list = await client.get("/api/v1/workspaces", headers=owner_headers)
    assert ws_list.status_code == 200
    assert len(ws_list.json()) >= 1

    # 2. Invite Bob as EDITOR
    invite_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "bob@example.com", "role": "EDITOR"},
        headers=owner_headers,
    )
    assert invite_res.status_code == 201
    assert invite_res.json()["role"] == "EDITOR"

    # 3. Create Project in Workspace (Bob is EDITOR, allowed)
    proj_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        json={"name": "Sprint 1 Core Backend", "description": "FastAPI migration"},
        headers=bob_headers,
    )
    assert proj_res.status_code == 201
    proj = proj_res.json()
    proj_id = proj["id"]

    # 4. Create Labels in Project
    lbl_res = await client.post(
        f"/api/v1/projects/{proj_id}/labels",
        json={"name": "Bug", "color": "#EF4444"},
        headers=bob_headers,
    )
    assert lbl_res.status_code == 201
    lbl_id = lbl_res.json()["id"]

    # 5. Create Task in Project with Assignee (Bob assigns to Owner)
    owner_info = (await client.get("/api/v1/users/me", headers=owner_headers)).json()
    task_res = await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        json={
            "title": "Setup PostgreSQL Database Connection",
            "description": "Configure async SQLAlchemy session",
            "status": "TODO",
            "priority": "HIGH",
            "assignee_id": owner_info["id"],
            "label_ids": [lbl_id],
        },
        headers=bob_headers,
    )
    assert task_res.status_code == 201
    task = task_res.json()
    task_id = task["id"]
    assert task["priority"] == "HIGH"
    assert len(task["labels"]) == 1

    # 6. List Tasks with Filters & Caching
    tasks_list = await client.get(
        f"/api/v1/projects/{proj_id}/tasks?status=TODO&priority=HIGH",
        headers=bob_headers,
    )
    assert tasks_list.status_code == 200
    assert len(tasks_list.json()["items"]) == 1

    # Second call hits cache
    cached_list = await client.get(
        f"/api/v1/projects/{proj_id}/tasks?status=TODO&priority=HIGH",
        headers=bob_headers,
    )
    assert cached_list.status_code == 200
    assert len(cached_list.json()["items"]) == 1

    # 7. Update Task Status -> IN_PROGRESS (triggers cache invalidation)
    patch_task = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "IN_PROGRESS"},
        headers=bob_headers,
    )
    assert patch_task.status_code == 200
    assert patch_task.json()["status"] == "IN_PROGRESS"

    # Filtering by TODO now returns 0 items (cache was properly invalidated!)
    empty_list = await client.get(
        f"/api/v1/projects/{proj_id}/tasks?status=TODO",
        headers=bob_headers,
    )
    assert len(empty_list.json()["items"]) == 0

    # 8. Add and List Comments on Task
    comment_res = await client.post(
        f"/api/v1/tasks/{task_id}/comments",
        json={"content": "Working on the connection pool configuration now."},
        headers=owner_headers,
    )
    assert comment_res.status_code == 201
    comment_id = comment_res.json()["id"]

    comments_list = await client.get(f"/api/v1/tasks/{task_id}/comments", headers=bob_headers)
    assert comments_list.status_code == 200
    assert len(comments_list.json()) == 1

    # 9. Archive Project
    archive_res = await client.patch(f"/api/v1/projects/{proj_id}/archive", headers=bob_headers)
    assert archive_res.status_code == 200
    assert archive_res.json()["status"] == "ARCHIVED"

    # 10. Delete Comment
    del_comment = await client.delete(f"/api/v1/comments/{comment_id}", headers=owner_headers)
    assert del_comment.status_code == 204

    # 11. Delete Task
    del_task = await client.delete(f"/api/v1/tasks/{task_id}", headers=bob_headers)
    assert del_task.status_code == 204


@pytest.mark.asyncio
async def test_rbac_permissions(client: AsyncClient):
    # Create Owner and Viewer
    await client.post(
        "/api/v1/auth/register",
        json={"email": "rbac_owner@example.com", "full_name": "RBAC Owner", "password": "pass123456"},
    )
    owner_token = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "rbac_owner@example.com", "password": "pass123456"},
        )
    ).json()["access_token"]
    owner_hdr = {"Authorization": f"Bearer {owner_token}"}

    await client.post(
        "/api/v1/auth/register",
        json={"email": "rbac_viewer@example.com", "full_name": "RBAC Viewer", "password": "pass123456"},
    )
    viewer_token = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "rbac_viewer@example.com", "password": "pass123456"},
        )
    ).json()["access_token"]
    viewer_hdr = {"Authorization": f"Bearer {viewer_token}"}

    # Owner creates workspace
    ws_res = await client.post(
        "/api/v1/workspaces", json={"name": "Secure Workspace"}, headers=owner_hdr
    )
    ws_id = ws_res.json()["id"]

    # Owner invites viewer as VIEWER
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "rbac_viewer@example.com", "role": "VIEWER"},
        headers=owner_hdr,
    )

    # Viewer tries to create project -> Should fail (403 Forbidden)
    fail_proj = await client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        json={"name": "Viewer Not Allowed Project"},
        headers=viewer_hdr,
    )
    assert fail_proj.status_code == 403

    # Viewer tries to delete workspace -> Should fail (403 Forbidden)
    fail_del_ws = await client.delete(f"/api/v1/workspaces/{ws_id}", headers=viewer_hdr)
    assert fail_del_ws.status_code == 403
