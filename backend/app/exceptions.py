"""
Custom application exceptions with structured error handling.
"""

from typing import Any, Optional


class AppError(Exception):
    def __init__(
        self,
        message: str = "An application error occurred",
        status_code: int = 500,
        details: Optional[Any] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", details: Optional[Any] = None):
        super().__init__(message=message, status_code=404, details=details)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation error", details: Optional[Any] = None):
        super().__init__(message=message, status_code=422, details=details)


class AutomationError(AppError):
    def __init__(self, message: str = "Automation error occurred", details: Optional[Any] = None):
        super().__init__(message=message, status_code=500, details=details)


class PrintError(AppError):
    def __init__(self, message: str = "Print error occurred", details: Optional[Any] = None):
        super().__init__(message=message, status_code=500, details=details)


class LoginError(AppError):
    def __init__(self, message: str = "Login failed", details: Optional[Any] = None):
        super().__init__(message=message, status_code=401, details=details)


class NetworkError(AppError):
    def __init__(self, message: str = "Network error occurred", details: Optional[Any] = None):
        super().__init__(message=message, status_code=503, details=details)
