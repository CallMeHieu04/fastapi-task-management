from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import DEFAULT_LABEL_COLOR, LABEL_COLOR_MAX_LENGTH, LABEL_NAME_MAX_LENGTH
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.task import Task


class Label(Base):
    __tablename__ = "labels"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_labels_project_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(LABEL_NAME_MAX_LENGTH), nullable=False)
    color: Mapped[str] = mapped_column(String(LABEL_COLOR_MAX_LENGTH), nullable=False, default=DEFAULT_LABEL_COLOR)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="labels")
    tasks: Mapped[list["Task"]] = relationship("Task", secondary="task_labels", back_populates="labels")
