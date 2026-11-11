# ==============================================================================
# Model & Schema Field Constraints
# ==============================================================================

# User & Password (Bcrypt byte limit is 72 bytes, min 8 characters)
USER_NAME_MIN_LENGTH = 2
USER_NAME_MAX_LENGTH = 100
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_BYTES = 72

# Workspace
WORKSPACE_NAME_MIN_LENGTH = 1
WORKSPACE_NAME_MAX_LENGTH = 255

# Project
PROJECT_NAME_MIN_LENGTH = 1
PROJECT_NAME_MAX_LENGTH = 255
PROJECT_DESC_MAX_LENGTH = 1000

# Task
TASK_TITLE_MIN_LENGTH = 1
TASK_TITLE_MAX_LENGTH = 255
TASK_DESC_MAX_LENGTH = 5000

# Label
LABEL_NAME_MIN_LENGTH = 1
LABEL_NAME_MAX_LENGTH = 100
HEX_COLOR_REGEX = r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$"

# Comment
COMMENT_CONTENT_MIN_LENGTH = 1
COMMENT_CONTENT_MAX_LENGTH = 2000

# Pagination
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Cache
DEFAULT_CACHE_TTL_SECONDS = 120

# ==============================================================================
# Business Error Messages (Gom tập trung, tránh hardcode lặp lại)
# ==============================================================================

MSG_TASK_NOT_FOUND = "Task #{id} not found."
MSG_PROJECT_NOT_FOUND = "Project #{id} not found."
MSG_WORKSPACE_NOT_FOUND = "Workspace #{id} not found."
MSG_USER_NOT_FOUND = "User #{id} not found."
MSG_LABEL_NOT_FOUND = "Label #{id} not found."
MSG_LABEL_NOT_IN_PROJECT = "Label #{id} not found in this project."
MSG_COMMENT_NOT_FOUND = "Comment #{id} not found."

# Authentication & Security Messages
MSG_EMAIL_EXISTS = "A user with this email address already exists."
MSG_EMAIL_IN_USE = "Email is already in use by another account."
MSG_INVALID_CREDENTIALS = "Incorrect email or password."
MSG_USER_INACTIVE = "User account is inactive."
MSG_TOKEN_REVOKED = "Refresh token has been revoked."
MSG_TOKEN_EXPIRED = "Refresh token has expired."
MSG_TOKEN_REUSED_REVOKED = "Token reuse detected. All sessions revoked."
MSG_INVALID_TOKEN = "Invalid or expired token."
MSG_INVALID_TOKEN_TYPE = "Invalid token type."
MSG_ACCESS_TOKEN_REQUIRED = "Invalid token type. Access token expected."
MSG_REFRESH_TOKEN_REQUIRED = "Invalid token type. Refresh token expected."
MSG_COULD_NOT_VALIDATE = "Could not validate credentials."
MSG_PASSWORD_MISMATCH = "Current password does not match."
MSG_CANNOT_DELETE_SELF = "You cannot delete your own account."
MSG_CANNOT_DELETE_LAST_ADMIN = "Cannot delete the last active administrator."
MSG_ADMIN_REQUIRED = "Administrator privileges are required for this operation."

# Authorization & Workspace Messages
MSG_WORKSPACE_ACCESS_DENIED = "You do not have access to this workspace."
MSG_OWNER_REQUIRED = "Only workspace OWNER can perform this action."
MSG_VIEWER_CANNOT_MODIFY = "Workspace VIEWERS are not permitted to modify this resource."
MSG_CANNOT_REMOVE_OWNER = "Cannot remove the owner from their own workspace."
MSG_OWNER_ALREADY_MEMBER = "The workspace owner already has full OWNER permissions."
MSG_MEMBER_NOT_FOUND = "Member not found in workspace."
MSG_DELETE_OWN_COMMENT_ONLY = "You can only delete your own comments."

# Validation error messages
MSG_CANNOT_BE_NULL = "{field} cannot be null when provided."
MSG_CANNOT_BE_BLANK = "{field} cannot be empty or only whitespace."
