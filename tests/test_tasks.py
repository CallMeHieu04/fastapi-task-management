from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import NotFoundException
from app.repositories.task_repository import TaskRepository
from app.services.task_service import TaskService


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_list_tasks_pagination(client: TestClient):
    response = client.get("/api/v1/tasks?page=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["meta"]["page"] == 1
    assert data["meta"]["page_size"] == 2
    assert data["meta"]["total"] >= 3


def test_list_tasks_filtering(client: TestClient):
    response = client.get("/api/v1/tasks?status=DONE")
    assert response.status_code == 200
    items = response.json()["items"]
    assert all(item["status"] == "DONE" for item in items)


def test_create_task_success(client: TestClient):
    payload = {
        "title": "Design Database Schema",
        "description": "Prepare ERD for workspaces and projects.",
        "status": "TODO",
        "priority": "HIGH",
    }
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["id"] > 0
    assert created["title"] == payload["title"]
    assert created["status"] == "TODO"


def test_create_task_whitespace_title_rejected(client: TestClient):
    response = client.post("/api/v1/tasks", json={"title": "   "})
    assert response.status_code == 422


def test_get_task_by_id(client: TestClient):
    response = client.get("/api/v1/tasks/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_get_task_not_found(client: TestClient):
    response = client.get("/api/v1/tasks/99999")
    assert response.status_code == 404
    assert "Task #99999 not found" in response.json()["detail"]


def test_patch_task_valid(client: TestClient):
    update_payload = {"status": "IN_PROGRESS", "priority": "URGENT"}
    response = client.patch("/api/v1/tasks/1", json=update_payload)
    assert response.status_code == 200
    updated = response.json()
    assert updated["status"] == "IN_PROGRESS"
    assert updated["priority"] == "URGENT"


def test_patch_task_null_title_rejected(client: TestClient):
    """Ensure explicit null on title returns 422 instead of corrupting data (500)."""
    response = client.patch("/api/v1/tasks/1", json={"title": None})
    assert response.status_code == 422


def test_patch_task_whitespace_title_rejected(client: TestClient):
    """Ensure whitespace title returns 422."""
    response = client.patch("/api/v1/tasks/1", json={"title": "   "})
    assert response.status_code == 422


def test_delete_task(client: TestClient):
    response = client.delete("/api/v1/tasks/1")
    assert response.status_code == 204

    get_res = client.get("/api/v1/tasks/1")
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_service_with_mock_repository():
    """Verify service uses injected self.repository rather than a global instance."""
    mock_repo = AsyncMock(spec=TaskRepository)
    mock_repo.get_by_id.return_value = None

    service = TaskService(repository=mock_repo)

    with pytest.raises(NotFoundException):
        await service.get_task(task_id=123)

    mock_repo.get_by_id.assert_called_once_with(123)
