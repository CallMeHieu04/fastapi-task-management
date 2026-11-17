import pytest
from httpx import AsyncClient


async def create_user_and_token(
    client: AsyncClient,
    email: str,
    name: str,
    password: str = "Password123!",
) -> tuple[str, int]:
    """Helper to register and login a test user, returning access token and user ID."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": name, "password": password},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.json()["access_token"]
    me_res = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me_res.json()["id"]
    return token, user_id


@pytest.mark.asyncio
async def test_workspace_project_rbac_and_crud(client: AsyncClient):
    """Test Project creation, listing, updating, deletion, and RBAC within a Workspace."""
    token_owner, owner_id = await create_user_and_token(client, "proj_owner@example.com", "Project Owner")
    token_editor, editor_id = await create_user_and_token(client, "proj_editor@example.com", "Project Editor")
    token_viewer, viewer_id = await create_user_and_token(client, "proj_viewer@example.com", "Project Viewer")
    token_outsider, _ = await create_user_and_token(client, "proj_outsider@example.com", "Project Outsider")

    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_editor = {"Authorization": f"Bearer {token_editor}"}
    headers_viewer = {"Authorization": f"Bearer {token_viewer}"}
    headers_outsider = {"Authorization": f"Bearer {token_outsider}"}

    # 1. Owner creates workspace
    ws_res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Sprint 5 Workspace"},
        headers=headers_owner,
    )
    ws_id = ws_res.json()["id"]

    # 2. Add Editor and Viewer to workspace
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "proj_editor@example.com", "role": "EDITOR"},
        headers=headers_owner,
    )
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "proj_viewer@example.com", "role": "VIEWER"},
        headers=headers_owner,
    )

    # 3. Viewer attempts to create project -> 403 Forbidden
    viewer_create = await client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        json={"name": "Viewer Project"},
        headers=headers_viewer,
    )
    assert viewer_create.status_code == 403

    # 4. Outsider attempts to create project -> 403 Forbidden
    outsider_create = await client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        json={"name": "Outsider Project"},
        headers=headers_outsider,
    )
    assert outsider_create.status_code == 403

    # 5. Editor creates project -> 201 Created
    editor_create = await client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        json={"name": "Backend Refactor", "description": "Refactor tasks module"},
        headers=headers_editor,
    )
    assert editor_create.status_code == 201
    project = editor_create.json()
    proj_id = project["id"]
    assert project["name"] == "Backend Refactor"
    assert project["workspace_id"] == ws_id

    # 6. Viewer lists projects in workspace -> 200 OK
    viewer_list = await client.get(f"/api/v1/workspaces/{ws_id}/projects", headers=headers_viewer)
    assert viewer_list.status_code == 200
    assert len(viewer_list.json()) == 1

    # 7. Viewer gets project by ID -> 200 OK
    viewer_get = await client.get(f"/api/v1/projects/{proj_id}", headers=headers_viewer)
    assert viewer_get.status_code == 200
    assert viewer_get.json()["id"] == proj_id

    # 8. Outsider gets project by ID -> 403 Forbidden
    outsider_get = await client.get(f"/api/v1/projects/{proj_id}", headers=headers_outsider)
    assert outsider_get.status_code == 403

    # 9. Viewer attempts to update project -> 403 Forbidden
    viewer_update = await client.patch(
        f"/api/v1/projects/{proj_id}",
        json={"name": "Viewer Malicious Name"},
        headers=headers_viewer,
    )
    assert viewer_update.status_code == 403

    # 10. Editor updates project -> 200 OK
    editor_update = await client.patch(
        f"/api/v1/projects/{proj_id}",
        json={"name": "Backend Refactor 2.0", "status": "ACTIVE"},
        headers=headers_editor,
    )
    assert editor_update.status_code == 200
    assert editor_update.json()["name"] == "Backend Refactor 2.0"

    # 11. Validation: PATCH with blank or null name -> 422
    blank_name = await client.patch(
        f"/api/v1/projects/{proj_id}",
        json={"name": "   "},
        headers=headers_editor,
    )
    assert blank_name.status_code == 422

    null_name = await client.patch(
        f"/api/v1/projects/{proj_id}",
        json={"name": None},
        headers=headers_editor,
    )
    assert null_name.status_code == 422


@pytest.mark.asyncio
async def test_task_management_in_project_and_rbac(client: AsyncClient):
    """Test creating tasks inside a project, assignee assignment, and RBAC permissions."""
    token_owner, owner_id = await create_user_and_token(client, "task_owner@example.com", "Task Owner")
    token_editor, editor_id = await create_user_and_token(client, "task_editor@example.com", "Task Editor")
    token_viewer, viewer_id = await create_user_and_token(client, "task_viewer@example.com", "Task Viewer")
    token_outsider, _ = await create_user_and_token(client, "task_outsider@example.com", "Task Outsider")

    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_editor = {"Authorization": f"Bearer {token_editor}"}
    headers_viewer = {"Authorization": f"Bearer {token_viewer}"}
    headers_outsider = {"Authorization": f"Bearer {token_outsider}"}

    # Workspace & Project setup
    ws_res = await client.post("/api/v1/workspaces", json={"name": "Delivery WS"}, headers=headers_owner)
    ws_id = ws_res.json()["id"]

    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "task_editor@example.com", "role": "EDITOR"},
        headers=headers_owner,
    )
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "task_viewer@example.com", "role": "VIEWER"},
        headers=headers_owner,
    )

    proj_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        json={"name": "Release v1.0"},
        headers=headers_owner,
    )
    proj_id = proj_res.json()["id"]

    # 1. Viewer attempts to create task in project -> 403 Forbidden
    viewer_task_fail = await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        json={"title": "Viewer Task"},
        headers=headers_viewer,
    )
    assert viewer_task_fail.status_code == 403

    # 2. Outsider attempts to create task in project -> 403 Forbidden
    outsider_task_fail = await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        json={"title": "Outsider Task"},
        headers=headers_outsider,
    )
    assert outsider_task_fail.status_code == 403

    # 3. Create task with invalid assignee_id -> 404 Not Found
    invalid_assignee = await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        json={"title": "Invalid Assignee Task", "assignee_id": 999999},
        headers=headers_editor,
    )
    assert invalid_assignee.status_code == 404

    # 4. Editor creates task in project with valid assignee -> 201 Created
    create_task_res = await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        json={
            "title": "Implement JWT rotation",
            "description": "Atomic refresh token rotation logic",
            "priority": "HIGH",
            "status": "TODO",
            "assignee_id": viewer_id,
        },
        headers=headers_editor,
    )
    assert create_task_res.status_code == 201
    task = create_task_res.json()
    assert task["id"] > 0
    assert task["title"] == "Implement JWT rotation"
    assert task["project_id"] == proj_id
    assert task["assignee_id"] == viewer_id
    assert task["created_by"] == editor_id
    assert task["priority"] == "HIGH"

    # 5. Viewer can read project tasks list -> 200 OK
    tasks_list_res = await client.get(f"/api/v1/projects/{proj_id}/tasks", headers=headers_viewer)
    assert tasks_list_res.status_code == 200
    assert tasks_list_res.json()["meta"]["total"] == 1

    # 6. Outsider cannot read project tasks list -> 403 Forbidden
    outsider_list_fail = await client.get(f"/api/v1/projects/{proj_id}/tasks", headers=headers_outsider)
    assert outsider_list_fail.status_code == 403


@pytest.mark.asyncio
async def test_task_update_delete_and_project_cascade(client: AsyncClient):
    """Test Task PATCH validation, RBAC checks, task deletion, and cascade delete on project removal."""
    token_owner, _ = await create_user_and_token(client, "cascade_owner@example.com", "Cascade Owner")
    token_editor, _ = await create_user_and_token(client, "cascade_editor@example.com", "Cascade Editor")
    token_viewer, _ = await create_user_and_token(client, "cascade_viewer@example.com", "Cascade Viewer")

    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_editor = {"Authorization": f"Bearer {token_editor}"}
    headers_viewer = {"Authorization": f"Bearer {token_viewer}"}

    # Workspace & Project setup
    ws = (
        await client.post(
            "/api/v1/workspaces",
            json={"name": "Cascade WS"},
            headers=headers_owner,
        )
    ).json()
    ws_id = ws["id"]

    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "cascade_editor@example.com", "role": "EDITOR"},
        headers=headers_owner,
    )
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "cascade_viewer@example.com", "role": "VIEWER"},
        headers=headers_owner,
    )

    proj = (
        await client.post(
            f"/api/v1/workspaces/{ws_id}/projects",
            json={"name": "Cascade Project"},
            headers=headers_owner,
        )
    ).json()
    proj_id = proj["id"]

    # Editor creates task
    task = (
        await client.post(
            f"/api/v1/projects/{proj_id}/tasks",
            json={"title": "Cascade Target Task", "status": "TODO"},
            headers=headers_editor,
        )
    ).json()
    task_id = task["id"]

    # 1. Viewer attempts to update task -> 403 Forbidden
    viewer_patch = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "IN_PROGRESS"},
        headers=headers_viewer,
    )
    assert viewer_patch.status_code == 403

    # 2. Editor updates task status & priority -> 200 OK
    editor_patch = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "DONE", "priority": "URGENT"},
        headers=headers_editor,
    )
    assert editor_patch.status_code == 200
    assert editor_patch.json()["status"] == "DONE"
    assert editor_patch.json()["priority"] == "URGENT"

    # 3. Explicit null validations -> 422
    null_title = await client.patch(f"/api/v1/tasks/{task_id}", json={"title": None}, headers=headers_editor)
    assert null_title.status_code == 422

    null_status = await client.patch(f"/api/v1/tasks/{task_id}", json={"status": None}, headers=headers_editor)
    assert null_status.status_code == 422

    null_priority = await client.patch(f"/api/v1/tasks/{task_id}", json={"priority": None}, headers=headers_editor)
    assert null_priority.status_code == 422

    blank_title = await client.patch(f"/api/v1/tasks/{task_id}", json={"title": "   "}, headers=headers_editor)
    assert blank_title.status_code == 422

    # 4. Viewer attempts to delete task -> 403 Forbidden
    viewer_del = await client.delete(f"/api/v1/tasks/{task_id}", headers=headers_viewer)
    assert viewer_del.status_code == 403

    # 5. Editor deletes task -> 204 No Content
    editor_del = await client.delete(f"/api/v1/tasks/{task_id}", headers=headers_editor)
    assert editor_del.status_code == 204

    # Verify task is deleted
    get_del = await client.get(f"/api/v1/tasks/{task_id}", headers=headers_editor)
    assert get_del.status_code == 404

    # 6. Cascade test: Create a new task in project, delete project -> task is also deleted
    new_task = (
        await client.post(
            f"/api/v1/projects/{proj_id}/tasks",
            json={"title": "Task to be cascaded"},
            headers=headers_editor,
        )
    ).json()
    new_task_id = new_task["id"]

    # Delete project
    del_proj = await client.delete(f"/api/v1/projects/{proj_id}", headers=headers_editor)
    assert del_proj.status_code == 204

    # Verify project is gone -> 404
    get_proj = await client.get(f"/api/v1/projects/{proj_id}", headers=headers_editor)
    assert get_proj.status_code == 404

    # Verify task was cascaded -> 404
    get_cascaded_task = await client.get(f"/api/v1/tasks/{new_task_id}", headers=headers_editor)
    assert get_cascaded_task.status_code == 404
