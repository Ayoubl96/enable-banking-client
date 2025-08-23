"""Custom exceptions for the Enable Banking client."""

from typing import Optional, Dict, Any


class EnableBankingError(Exception):
    """Base exception for all Enable Banking client errors."""
    pass


class HTTPClientError(EnableBankingError):
    """Base class for HTTP client errors."""
    
    def __init__(
        self, 
        message: str, 
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}
        self.request_id = request_id


class RateLimitError(HTTPClientError):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self, 
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class AuthenticationError(HTTPClientError):
    """Raised when authentication fails."""
    pass


class AuthorizationError(HTTPClientError):
    """Raised when authorization fails (403)."""
    pass


class NotFoundError(HTTPClientError):
    """Raised when resource is not found (404)."""
    pass


class ValidationError(HTTPClientError):
    """Raised when request validation fails (400)."""
    pass


class ServerError(HTTPClientError):
    """Raised when server returns 5xx error."""
    pass


class TimeoutError(HTTPClientError):
    """Raised when request times out."""
    pass


class ConnectionError(HTTPClientError):
    """Raised when connection fails."""
    pass


def create_http_error(
    status_code: int,
    message: str,
    response_data: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> HTTPClientError:
    """Create appropriate HTTP error based on status code."""
    
    error_classes = {
        400: ValidationError,
        401: AuthenticationError,
        403: AuthorizationError,
        404: NotFoundError,
        429: RateLimitError,
    }
    
    if status_code in error_classes:
        return error_classes[status_code](
            message=message,
            status_code=status_code,
            response_data=response_data,
            request_id=request_id
        )
    elif 500 <= status_code < 600:
        return ServerError(
            message=message,
            status_code=status_code,
            response_data=response_data,
            request_id=request_id
        )
    else:
        return HTTPClientError(
            message=message,
            status_code=status_code,
            response_data=response_data,
            request_id=request_id
        )