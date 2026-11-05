from datetime import UTC, datetime

from app.models.task import TaskModel, TaskPriority, TaskStatus


class TaskRepository:
    """In-memory data access layer storing internal TaskModel instances.

    Designed for clean dependency injection, easily swapped with a database repository later.
    """

    def __init__(self) -> None:
        self._storage: dict[int, TaskModel] = {}
        self._current_id: int = 0
        self._seed_data()

    def _seed_data(self) -> None:
        now = datetime.now(UTC)
        initial_tasks = [
            (
                "Setup FastAPI Layered Architecture",
                "Organize project into api, core, models, schemas, repositories, and services.",
                TaskStatus.DONE,
                TaskPriority.HIGH,
            ),
            (
                "Implement Task CRUD Endpoints",
                "Create GET, POST, PATCH, DELETE endpoints with Pydantic v2 schemas.",
                TaskStatus.IN_PROGRESS,
                TaskPriority.HIGH,
            ),
            (
                "Add Request Validation & Error Handling",
                "Prevent null/whitespace PATCH requests and register domain exceptions.",
                TaskStatus.TODO,
                TaskPriority.MEDIUM,
            ),
        ]
        for title, desc, status, priority in initial_tasks:
            self._current_id += 1
            self._storage[self._current_id] = TaskModel(
                id=self._current_id,
                title=title,
                description=desc,
                status=status,
                priority=priority,
                due_date=None,
                created_at=now,
                updated_at=now,
            )

    async def get_by_id(self, task_id: int) -> TaskModel | None:
        return self._storage.get(task_id)

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        search: str | None = None,
    ) -> tuple[list[TaskModel], int]:
        items = list(self._storage.values())

        if status:
            items = [t for t in items if t.status == status]
        if priority:
            items = [t for t in items if t.priority == priority]
        if search:
            query = search.lower()
            items = [t for t in items if query in t.title.lower() or (t.description and query in t.description.lower())]

        total = len(items)
        paged = items[skip : skip + limit]
        return paged, total

    async def create(
        self,
        title: str,
        description: str | None,
        status: TaskStatus,
        priority: TaskPriority,
        due_date: datetime | None,
    ) -> TaskModel:
        self._current_id += 1
        now = datetime.now(UTC)
        model = TaskModel(
            id=self._current_id,
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_date=due_date,
            created_at=now,
            updated_at=now,
        )
        self._storage[self._current_id] = model
        return model

    async def update(self, task_id: int, update_data: dict) -> TaskModel | None:
        task = self._storage.get(task_id)
        if not task:
            return None

        for field, value in update_data.items():
            if hasattr(task, field):
                setattr(task, field, value)
        task.updated_at = datetime.now(UTC)
        return task

    async def delete(self, task_id: int) -> bool:
        if task_id in self._storage:
            del self._storage[task_id]
            return True
        return False
