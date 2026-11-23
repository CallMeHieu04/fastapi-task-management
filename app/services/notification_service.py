import logging
from typing import Any

logger = logging.getLogger("app.notifications")


class NotificationService:
    """Service handling asynchronous background notifications and email simulations.

    Designed to be invoked via FastAPI's BackgroundTasks without blocking HTTP response cycles.
    """

    # In-memory audit log of executed background tasks (useful for testing and observability)
    dispatched_events: list[dict[str, Any]] = []

    @classmethod
    def record_event(cls, event_type: str, payload: dict[str, Any]) -> None:
        """Record dispatched background event for tracking and assertions."""
        cls.dispatched_events.append({"event_type": event_type, "payload": payload})

    @classmethod
    async def send_welcome_email(cls, email: str, full_name: str) -> None:
        """Simulate sending a welcome email to a newly registered user."""
        logger.info("Sent welcome email to %s (%s)", email, full_name)
        cls.record_event("welcome_email", {"email": email, "full_name": full_name})

    @classmethod
    async def send_task_assignment_notification(
        cls,
        task_id: int,
        task_title: str,
        assignee_email: str,
    ) -> None:
        """Simulate sending a notification when a task is assigned to a member."""
        logger.info("Task #%d '%s' assigned to %s", task_id, task_title, assignee_email)
        cls.record_event(
            "task_assignment",
            {"task_id": task_id, "task_title": task_title, "assignee_email": assignee_email},
        )

    @classmethod
    async def send_task_status_update_notification(
        cls,
        task_id: int,
        task_title: str,
        old_status: str,
        new_status: str,
        recipient_email: str | None = None,
    ) -> None:
        """Simulate sending a notification when a task's status changes."""
        logger.info("Task #%d status changed: %s -> %s", task_id, old_status, new_status)
        cls.record_event(
            "task_status_update",
            {
                "task_id": task_id,
                "task_title": task_title,
                "old_status": old_status,
                "new_status": new_status,
                "recipient_email": recipient_email,
            },
        )

    @classmethod
    async def send_workspace_invitation(
        cls,
        email: str,
        workspace_name: str,
        role: str,
    ) -> None:
        """Simulate sending an invitation email when a user is added to a workspace."""
        logger.info("Sent workspace invitation to %s for %s (%s)", email, workspace_name, role)
        cls.record_event(
            "workspace_invitation",
            {"email": email, "workspace_name": workspace_name, "role": role},
        )

    @classmethod
    async def send_task_reminder(
        cls,
        task_id: int,
        task_title: str,
        assignee_email: str,
        custom_message: str | None = None,
    ) -> None:
        """Simulate sending a reminder for an upcoming or pending task."""
        msg = custom_message or "Please review and update your progress on this task."
        logger.info("Sent task reminder for task #%d to %s", task_id, assignee_email)
        cls.record_event(
            "task_reminder",
            {
                "task_id": task_id,
                "task_title": task_title,
                "assignee_email": assignee_email,
                "message": msg,
            },
        )
