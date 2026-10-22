"""
Exception definitions for ShopFlow integration.
"""

from typing import Any, Dict, Optional
from fastapi import status
from app.core import constants
from app.core.exceptions import AppException


class ShopFlowError(AppException):
    """Base exception for all ShopFlow integration errors."""

    def __init__(
        self,
        message: str = "An error occurred while communicating with ShopFlow",
        status_code: int = status.HTTP_502_BAD_GATEWAY,
        code: str = constants.ERR_EXTERNAL_SERVICE,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            code=code,
            message=message,
            status_code=status_code,
            details=details,
        )


class ShopFlowNotConfiguredError(ShopFlowError):
    """Raised when ShopFlow service credentials or base URL are missing."""

    def __init__(
        self,
        message: str = "ShopFlow service integration is not configured",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            code=constants.ERR_CONFIGURATION,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


class ShopFlowConnectionError(ShopFlowError):
    """Raised when connecting to ShopFlow fails (network unreachable, refused)."""

    def __init__(
        self,
        message: str = "Unable to connect to ShopFlow service",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            code=constants.ERR_EXTERNAL_SERVICE,
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details,
        )


class ShopFlowTimeoutError(ShopFlowError):
    """Raised when a request to ShopFlow times out."""

    def __init__(
        self,
        message: str = "ShopFlow request timed out",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            code=constants.ERR_EXTERNAL_SERVICE,
            message=message,
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            details=details,
        )


class ShopFlowAuthError(ShopFlowError):
    """Raised when ShopFlow rejects internal service authentication (401/403)."""

    def __init__(
        self,
        message: str = "ShopFlow service authentication failed",
        status_code: int = status.HTTP_502_BAD_GATEWAY,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            code=constants.ERR_EXTERNAL_SERVICE,
            message=message,
            status_code=status_code,
            details=details,
        )


class ShopFlowNotFoundError(ShopFlowError):
    """Raised when a requested resource is not found in ShopFlow (404)."""

    def __init__(
        self,
        message: str = "Requested resource not found in ShopFlow",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            code=constants.ERR_NOT_FOUND,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ShopFlowValidationError(ShopFlowError):
    """Raised when ShopFlow rejects a request due to validation errors (422)."""

    def __init__(
        self,
        message: str = "ShopFlow validation error",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            code=constants.ERR_VALIDATION,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class ShopFlowConflictError(ShopFlowError):
    """Raised when ShopFlow rejects a request due to business conflict (409)."""

    def __init__(
        self,
        message: str = "Conflict with existing ShopFlow resource",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            code="CONFLICT_ERROR",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class ShopFlowRateLimitError(ShopFlowError):
    """Raised when ShopFlow rate limits the request (429)."""

    def __init__(
        self,
        message: str = "ShopFlow service rate limit exceeded",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            code=constants.ERR_RATE_LIMIT,
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )


class ShopFlowServerError(ShopFlowError):
    """Raised when ShopFlow experiences an internal server error (5xx)."""

    def __init__(
        self,
        message: str = "ShopFlow internal service error",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            code=constants.ERR_EXTERNAL_SERVICE,
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details,
        )
