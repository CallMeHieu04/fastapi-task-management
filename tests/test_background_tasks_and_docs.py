import pytest
from httpx import AsyncClient

from app.services.notification_service import NotificationService
from tests.conftest import create_user_and_token


@pytest.fixture(autouse=True)
def clear_notification_events():
    """Clear in-memory notification events before and after each test."""
    NotificationService.dispatched_events.clear()
    yield
    NotificationService.dispatched_events.clear()


@pytest.mark.asyncio
async def test_welcome_email_background_task_on_register(client: AsyncClient):
    """Test that registering a new account triggers an async welcome email."""
    res = await client.post(
        "/api/v1/auth/register",
        json={"email": "newuser@example.com", "full_name": "New User", "password": "Password123!"},
    )
    assert res.status_code == 201

    # Verify background task dispatched
    welcome_events = [e for e in NotificationService.dispatched_events if e["event_type"] == "welcome_email"]
    assert len(welcome_events) == 1
    assert welcome_events[0]["payload"]["email"] == "newuser@example.com"
    assert welcome_events[0]["payload"]["full_name"] == "New User"


@pytest.mark.asyncio
async def test_workspace_invitation_background_task(client: AsyncClient):
    """Test that adding a member to a workspace triggers an async invitation email."""
    owner_token, _ = await create_user_and_token(client, "inv_owner@example.com", "Inv Owner")
    _, member_id = await create_user_and_token(client, "inv_member@example.com", "Inv Member")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    ws = (await client.post("/api/v1/workspaces", json={"name": "Inv Workspace"}, headers=owner_headers)).json()
    ws_id = ws["id"]

    res = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": member_id, "role": "EDITOR"},
        headers=owner_headers,
    )
    assert res.status_code == 201

    inv_events = [e for e in NotificationService.dispatched_events if e["event_type"] == "workspace_invitation"]
    assert len(inv_events) >= 1
    last_inv = inv_events[-1]
    assert last_inv["payload"]["email"] == "inv_member@example.com"
    assert last_inv["payload"]["role"] == "EDITOR"


@pytest.mark.asyncio
async def test_task_assignment_and_status_update_background_tasks(client: AsyncClient):
    """Test that assigning a task and updating its status trigger background notifications."""
    token, _ = await create_user_and_token(client, "task_bg_owner@example.com", "Task Owner")
    _, dev_id = await create_user_and_token(client, "task_bg_dev@example.com", "Task Dev")
    headers = {"Authorization": f"Bearer {token}"}

    ws = (await client.post("/api/v1/workspaces", json={"name": "Task BG WS"}, headers=headers)).json()
    ws_id = ws["id"]

    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": dev_id, "role": "EDITOR"},
        headers=headers,
    )

    proj = (await client.post(f"/api/v1/workspaces/{ws_id}/projects", json={"name": "BG Proj"}, headers=headers)).json()

    # 1. Create task with assignee -> assignment notification
    t_res = await client.post(
        f"/api/v1/projects/{proj['id']}/tasks",
        json={"title": "Important Background Task", "assignee_id": dev_id},
        headers=headers,
    )
    assert t_res.status_code == 201
    task_id = t_res.json()["id"]

    assign_events = [e for e in NotificationService.dispatched_events if e["event_type"] == "task_assignment"]
    assert len(assign_events) >= 1
    assert assign_events[-1]["payload"]["task_id"] == task_id
    assert assign_events[-1]["payload"]["assignee_email"] == "task_bg_dev@example.com"

    # 2. Update task status -> status update notification
    patch_res = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "IN_PROGRESS"},
        headers=headers,
    )
    assert patch_res.status_code == 200

    status_events = [e for e in NotificationService.dispatched_events if e["event_type"] == "task_status_update"]
    assert len(status_events) >= 1
    assert status_events[-1]["payload"]["task_id"] == task_id
    assert status_events[-1]["payload"]["new_status"] == "IN_PROGRESS"


@pytest.mark.asyncio
async def test_task_reminder_endpoint(client: AsyncClient):
    """Test POST /api/v1/tasks/{id}/remind endpoint."""
    token, _ = await create_user_and_token(client, "remind_owner@example.com", "Remind Owner")
    _, dev_id = await create_user_and_token(client, "remind_dev@example.com", "Remind Dev")
    headers = {"Authorization": f"Bearer {token}"}

    ws = (await client.post("/api/v1/workspaces", json={"name": "Remind WS"}, headers=headers)).json()
    await client.post(
        f"/api/v1/workspaces/{ws['id']}/members",
        json={"user_id": dev_id, "role": "EDITOR"},
        headers=headers,
    )
    proj = (
        await client.post(f"/api/v1/workspaces/{ws['id']}/projects", json={"name": "Remind Proj"}, headers=headers)
    ).json()

    # Task without assignee
    t_no_ass = (
        await client.post(f"/api/v1/projects/{proj['id']}/tasks", json={"title": "Unassigned Task"}, headers=headers)
    ).json()

    # Remind unassigned task -> 400 Bad Request
    remind_bad = await client.post(f"/api/v1/tasks/{t_no_ass['id']}/remind", headers=headers)
    assert remind_bad.status_code == 400

    # Task with assignee
    t_ass = (
        await client.post(
            f"/api/v1/projects/{proj['id']}/tasks",
            json={"title": "Assigned Task", "assignee_id": dev_id},
            headers=headers,
        )
    ).json()

    # Remind assigned task -> 200 OK + task_reminder event
    remind_ok = await client.post(f"/api/v1/tasks/{t_ass['id']}/remind", headers=headers)
    assert remind_ok.status_code == 200
    assert "Reminder queued" in remind_ok.json()["message"]

    reminder_events = [e for e in NotificationService.dispatched_events if e["event_type"] == "task_reminder"]
    assert len(reminder_events) == 1
    assert reminder_events[0]["payload"]["task_id"] == t_ass["id"]
    assert reminder_events[0]["payload"]["assignee_email"] == "remind_dev@example.com"


@pytest.mark.asyncio
async def test_openapi_documentation_endpoints(client: AsyncClient):
    """Test that Swagger, Redoc, OpenAPI schema, and root health check return valid responses."""
    # 1. OpenAPI JSON Schema
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

    # 2. Swagger Docs HTML
    docs_res = await client.get("/docs")
    assert docs_res.status_code == 200

    # 3. Redoc HTML
    redoc_res = await client.get("/redoc")
    assert redoc_res.status_code == 200

    # 4. Root & Health
    root_res = await client.get("/")
    assert root_res.status_code == 200
    assert root_res.json()["status"] == "online"

    health_res = await client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"
