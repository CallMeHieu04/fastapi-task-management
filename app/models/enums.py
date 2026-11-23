import enum


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class WorkspaceMemberRole(str, enum.Enum):
    OWNER = "OWNER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


class ProjectStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class TaskStatus(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    DONE = "DONE"


class TaskPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TokenType(str, enum.Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class SortOrder(str, enum.Enum):
    ASC = "asc"
    DESC = "desc"


class TaskSortBy(str, enum.Enum):
    CREATED_AT = "created_at"
    DUE_DATE = "due_date"
    PRIORITY = "priority"
    TITLE = "title"
    STATUS = "status"
    UPDATED_AT = "updated_at"


class ProjectSortBy(str, enum.Enum):
    CREATED_AT = "created_at"
    NAME = "name"
    STATUS = "status"
