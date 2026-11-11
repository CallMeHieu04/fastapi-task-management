class AppException(Exception):
    """Base application exception for business logic errors."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundException(AppException):
    """Exception raised when a requested resource does not exist (404)."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=404)


class BadRequestException(AppException):
    """Exception raised for invalid client operations or conflicts (400)."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=400)


class UnauthorizedException(AppException):
    """Exception raised when authentication fails (401)."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=401)


class ForbiddenException(AppException):
    """Exception raised when user does not have required permissions (403)."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=403)


class ConflictException(AppException):
    """Exception raised when a resource conflict occurs, such as duplicate unique constraint (409)."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=409)
