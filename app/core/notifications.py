import asyncio
import logging

logger = logging.getLogger("app.notifications")


async def send_task_assignment_email(
    to_email: str,
    assignee_name: str,
    task_id: int,
    task_title: str,
    project_name: str,
    assigned_by_name: str,
) -> None:
    """Simulates sending an async email notification when a task is assigned.

    Executed in the background via FastAPI BackgroundTasks.
    """
    logger.info(
        f"[EMAIL NOTIFICATION] Sending task assignment email to {to_email}..."
    )
    # Simulate non-blocking network I/O
    await asyncio.sleep(0.05)

    subject = f"[TaskHub] You have been assigned to task #{task_id}: {task_title}"
    body = (
        f"Hello {assignee_name},\n\n"
        f"{assigned_by_name} has assigned you to the task '{task_title}' "
        f"in project '{project_name}'.\n\n"
        f"Best regards,\n"
        f"TaskHub Team"
    )

    logger.info(
        f"[EMAIL SENT] To: {to_email} | Subject: '{subject}' | Content: '{body.strip()}'"
    )
