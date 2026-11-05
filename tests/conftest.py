from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_task_repository
from app.main import app
from app.repositories.task_repository import TaskRepository


@pytest.fixture
def fresh_repo() -> TaskRepository:
    """Provides a fresh isolated repository instance for each test case."""
    return TaskRepository()


@pytest.fixture
def client(fresh_repo: TaskRepository) -> Generator[TestClient, None, None]:
    """Test client with isolated in-memory repository dependency override."""
    app.dependency_overrides[get_task_repository] = lambda: fresh_repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
