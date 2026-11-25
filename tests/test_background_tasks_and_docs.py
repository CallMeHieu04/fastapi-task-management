from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.core.constants import MSG_REMINDER_QUEUED
from app.services.notification_service import NotificationService
from tests.conftest import create_user_and_token


@pytest.mark.asyncio
async def test_welcome_email_background_task_on_register(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Test that registering a new account triggers an async welcome email."""
    mock_welcome = AsyncMock()
    monkeypatch.setattr(NotificationService, "send_welcome_email", mock_welcome)

    res = await client.post(
        "/api/v1/auth/register",
        json={"email": "newuser@example.com", "full_name": "New User", "password": "Password123!"},
    )
    assert res.status_code == 201
    user_id = res.json()["id"]

    mock_welcome.assert_awaited_once_with(user_id=user_id)


@pytest.mark.asyncio
async def test_workspace_invitation_background_task(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Test that adding a member to a workspace triggers an async invitation with real workspace name."""
    owner_token, _ = await create_user_and_token(client, "inv_owner@example.com", "Inv Owner")
    _, member_id = await create_user_and_token(client, "inv_member@example.com", "Inv Member")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    ws = (await client.post("/api/v1/workspaces", json={"name": "Inv Workspace"}, headers=owner_headers)).json()
    ws_id = ws["id"]

    mock_invite = AsyncMock()
    monkeypatch.setattr(NotificationService, "send_workspace_invitation", mock_invite)

    res = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": member_id, "role": "EDITOR"},
        headers=owner_headers,
    )
    assert res.status_code == 201

    mock_invite.assert_awaited_once_with(
        user_id=member_id,
        workspace_name="Inv Workspace",
        role="EDITOR",
    )


@pytest.mark.asyncio
async def test_task_assignment_and_status_update_background_tasks(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test task assignment, status change, no-op status PATCH, and assignee change notifications."""
    token, _ = await create_user_and_token(client, "task_bg_owner@example.com", "Task Owner")
    _, dev1_id = await create_user_and_token(client, "task_bg_dev1@example.com", "Task Dev 1")
    _, dev2_id = await create_user_and_token(client, "task_bg_dev2@example.com", "Task Dev 2")
    headers = {"Authorization": f"Bearer {token}"}

    ws = (await client.post("/api/v1/workspaces", json={"name": "Task BG WS"}, headers=headers)).json()
    ws_id = ws["id"]

    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": dev1_id, "role": "EDITOR"},
        headers=headers,
    )
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": dev2_id, "role": "EDITOR"},
        headers=headers,
    )

    proj = (await client.post(f"/api/v1/workspaces/{ws_id}/projects", json={"name": "BG Proj"}, headers=headers)).json()

    mock_assign = AsyncMock()
    mock_status = AsyncMock()
    monkeypatch.setattr(NotificationService, "send_task_assignment_notification", mock_assign)
    monkeypatch.setattr(NotificationService, "send_task_status_update_notification", mock_status)

    # 1. Create task with assignee -> assignment notification
    t_res = await client.post(
        f"/api/v1/projects/{proj['id']}/tasks",
        json={"title": "Important Background Task", "assignee_id": dev1_id},
        headers=headers,
    )
    assert t_res.status_code == 201
    task_id = t_res.json()["id"]

    mock_assign.assert_awaited_once_with(
        task_id=task_id,
        task_title="Important Background Task",
        assignee_id=dev1_id,
    )
    mock_assign.reset_mock()

    # 2. Update task status (TODO -> IN_PROGRESS) -> status update notification
    patch_res = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "IN_PROGRESS"},
        headers=headers,
    )
    assert patch_res.status_code == 200

    mock_status.assert_awaited_once_with(
        task_id=task_id,
        task_title="Important Background Task",
        old_status="TODO",
        new_status="IN_PROGRESS",
        recipient_id=dev1_id,
    )
    mock_status.reset_mock()

    # 3. PATCH same status (IN_PROGRESS -> IN_PROGRESS) -> must NOT send notification
    same_status_res = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "IN_PROGRESS"},
        headers=headers,
    )
    assert same_status_res.status_code == 200
    mock_status.assert_not_awaited()

    # 4. PATCH assignee_id to dev2 -> must send assignment notification to new assignee
    reassign_res = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"assignee_id": dev2_id},
        headers=headers,
    )
    assert reassign_res.status_code == 200
    mock_assign.assert_awaited_once_with(
        task_id=task_id,
        task_title="Important Background Task",
        assignee_id=dev2_id,
    )
    mock_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_task_reminder_endpoint_and_rbac(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Test POST /api/v1/tasks/{id}/remind permissions, validation, and non-PII response."""
    owner_token, _ = await create_user_and_token(client, "remind_owner@example.com", "Remind Owner")
    dev_token, dev_id = await create_user_and_token(client, "remind_dev@example.com", "Remind Dev")
    viewer_token, viewer_id = await create_user_and_token(client, "remind_viewer@example.com", "Remind Viewer")
    outsider_token, _ = await create_user_and_token(client, "remind_outsider@example.com", "Outsider")

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    dev_headers = {"Authorization": f"Bearer {dev_token}"}
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    outsider_headers = {"Authorization": f"Bearer {outsider_token}"}

    # Standalone task (no project) -> outsider must NOT be able to remind
    standalone = (
        await client.post(
            "/api/v1/tasks",
            json={"title": "Private Standalone Task", "assignee_id": dev_id},
            headers=owner_headers,
        )
    ).json()
    outsider_remind = await client.post(f"/api/v1/tasks/{standalone['id']}/remind", headers=outsider_headers)
    assert outsider_remind.status_code == 404

    # Project task setup
    ws = (await client.post("/api/v1/workspaces", json={"name": "Remind WS"}, headers=owner_headers)).json()
    await client.post(
        f"/api/v1/workspaces/{ws['id']}/members",
        json={"user_id": dev_id, "role": "EDITOR"},
        headers=owner_headers,
    )
    await client.post(
        f"/api/v1/workspaces/{ws['id']}/members",
        json={"user_id": viewer_id, "role": "VIEWER"},
        headers=owner_headers,
    )
    proj = (
        await client.post(
            f"/api/v1/workspaces/{ws['id']}/projects", json={"name": "Remind Proj"}, headers=owner_headers
        )
    ).json()

    # Task without assignee -> 400 Bad Request
    t_no_ass = (
        await client.post(
            f"/api/v1/projects/{proj['id']}/tasks",
            json={"title": "Unassigned Task"},
            headers=owner_headers,
        )
    ).json()
    remind_bad = await client.post(f"/api/v1/tasks/{t_no_ass['id']}/remind", headers=owner_headers)
    assert remind_bad.status_code == 400

    # Task with assignee
    t_ass = (
        await client.post(
            f"/api/v1/projects/{proj['id']}/tasks",
            json={"title": "Assigned Task", "assignee_id": dev_id},
            headers=owner_headers,
        )
    ).json()

    # VIEWER cannot remind -> 403 Forbidden
    viewer_remind = await client.post(f"/api/v1/tasks/{t_ass['id']}/remind", headers=viewer_headers)
    assert viewer_remind.status_code == 403

    # Outsider cannot remind -> 404 Not Found
    outsider_proj_remind = await client.post(f"/api/v1/tasks/{t_ass['id']}/remind", headers=outsider_headers)
    assert outsider_proj_remind.status_code == 404

    # EDITOR can remind -> 200 OK, response must NOT leak assignee email
    mock_reminder = AsyncMock()
    monkeypatch.setattr(NotificationService, "send_task_reminder", mock_reminder)

    remind_ok = await client.post(f"/api/v1/tasks/{t_ass['id']}/remind", headers=dev_headers)
    assert remind_ok.status_code == 200
    assert remind_ok.json()["message"] == MSG_REMINDER_QUEUED
    assert "remind_dev@example.com" not in remind_ok.text

    mock_reminder.assert_awaited_once_with(
        task_id=t_ass["id"],
        task_title="Assigned Task",
        assignee_id=dev_id,
    )


@pytest.mark.asyncio
async def test_openapi_documentation_endpoints(client: AsyncClient):
    """Test that Swagger, Redoc, OpenAPI schema, and root health check return valid responses."""
    openapi_res = await client.get("/api/v1/openapi.json")
    assert openapi_res.status_code == 200
    schema = openapi_res.json()
    assert "openapi" in schema
    assert "paths" in schema
    assert "/api/v1/tasks" in schema["paths"]
    assert "/api/v1/tasks/{id}/remind" in schema["paths"]
    assert "tags" in schema
    tag_names = [t["name"] for t in schema["tags"]]
    assert "Authentication" in tag_names
    assert "Tasks" in tag_names
    assert "Workspaces" in tag_names

    docs_res = await client.get("/docs")
    assert docs_res.status_code == 200

    redoc_res = await client.get("/redoc")
    assert redoc_res.status_code == 200

    root_res = await client.get("/")
    assert root_res.status_code == 200
    assert root_res.json()["status"] == "online"

    health_res = await client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"
