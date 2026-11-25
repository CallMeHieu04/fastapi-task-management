import logging

logger = logging.getLogger("app.notifications")


class NotificationService:
    """Service handling asynchronous background notifications.

    Designed to be invoked via FastAPI's BackgroundTasks without blocking HTTP response cycles.
    """

    @classmethod
    async def send_welcome_email(cls, user_id: int) -> None:
        """Simulate sending a welcome email to a newly registered user."""
        logger.info("Sent welcome email to user #%d", user_id)

    @classmethod
    async def send_task_assignment_notification(
        cls,
        task_id: int,
        task_title: str,
        assignee_id: int,
    ) -> None:
        """Simulate sending a notification when a task is assigned to a member."""
        logger.info("Task #%d '%s' assigned to user #%d", task_id, task_title, assignee_id)

    @classmethod
    async def send_task_status_update_notification(
        cls,
        task_id: int,
        task_title: str,
        old_status: str,
        new_status: str,
        recipient_id: int | None = None,
    ) -> None:
        """Simulate sending a notification when a task's status changes."""
        logger.info(
            "Task #%d '%s' status changed: %s -> %s (recipient user #%s)",
            task_id,
            task_title,
            old_status,
            new_status,
            recipient_id,
        )

    @classmethod
    async def send_workspace_invitation(
        cls,
        user_id: int,
        workspace_name: str,
        role: str,
    ) -> None:
        """Simulate sending an invitation email when a user is added to a workspace."""
        logger.info("Sent workspace invitation to user #%d for '%s' (%s)", user_id, workspace_name, role)

    @classmethod
    async def send_task_reminder(
        cls,
        task_id: int,
        task_title: str,
        assignee_id: int,
        custom_message: str | None = None,
    ) -> None:
        """Simulate sending a reminder for an upcoming or pending task."""
        logger.info("Sent task reminder for task #%d '%s' to user #%d", task_id, task_title, assignee_id)
