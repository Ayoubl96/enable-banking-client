import asyncio
import time
from typing import Dict, Any, Optional, Union, List
from urllib.parse import urljoin, urlencode
import httpx

from enable_banking.config.logging import get_logger, mask_sensitive_data
from enable_banking.config.settings import settings
from enable_banking.client.exceptions import (
    HTTPClientError,
    RateLimitError,
    TimeoutError,
    ConnectionError,
    create_http_error,
)

logger = get_logger(__name__)


class RateLimiter:
    """Rate limiter for API requests."""
    
    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.requests = []
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire rate limit permission."""
        async with self.lock:
            now = time.time()
            # Remove requests older than 1 minute
            self.requests = [req_time for req_time in self.requests if now - req_time < 60]
            
            if len(self.requests) >= self.requests_per_minute:
                # Calculate wait time
                oldest_request = min(self.requests)
                wait_time = 60 - (now - oldest_request) + 1  # Add 1 second buffer
                
                if wait_time > 0:
                    logger.warning(f"Rate limit reached, waiting {wait_time:.1f} seconds")
                    await asyncio.sleep(wait_time)
                    return await self.acquire()
            
            self.requests.append(now)


class HTTPClient:
    """HTTP client wrapper for Enable Banking API with rate limiting and retry logic."""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        auth_rate_limit: int = 10,  # 10 req/min for auth endpoints
        data_rate_limit: int = 100,  # 100 req/min for data endpoints
        max_retries: int = 3,
        retry_backoff_factor: float = 2.0,
    ):
        """Initialize HTTP client.
        
        Args:
            base_url: Base URL for API requests
            timeout: Request timeout in seconds
            auth_rate_limit: Rate limit for auth endpoints (per minute)
            data_rate_limit: Rate limit for data endpoints (per minute)
            max_retries: Maximum number of retries for failed requests
            retry_backoff_factor: Exponential backoff factor for retries
        """
        self.base_url = base_url or settings.enable_banking_base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor
        
        # Rate limiters
        self.auth_rate_limiter = RateLimiter(auth_rate_limit)
        self.data_rate_limiter = RateLimiter(data_rate_limit)
        
        # HTTP client
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={
                "User-Agent": "enable-banking-python-client/0.1.0",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            follow_redirects=True,
        )
        
        logger.info(f"HTTP client initialized with base URL: {self.base_url}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
        logger.debug("HTTP client closed")
    
    def _get_rate_limiter(self, endpoint: str) -> RateLimiter:
        """Get appropriate rate limiter based on endpoint."""
        auth_endpoints = ["/auth", "/sessions", "/application"]
        
        for auth_endpoint in auth_endpoints:
            if auth_endpoint in endpoint:
                return self.auth_rate_limiter
        
        return self.data_rate_limiter
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint."""
        return urljoin(self.base_url, endpoint.lstrip('/'))
    
    def _sanitize_for_logging(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize sensitive data for logging."""
        if not data:
            return {}
        
        sensitive_fields = [
            "authorization", "token", "password", "secret", "key",
            "account_number", "iban", "card_number", "cvv"
        ]
        
        sanitized = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(field in key_lower for field in sensitive_fields):
                if isinstance(value, str):
                    sanitized[key] = mask_sensitive_data(value)
                else:
                    sanitized[key] = "[MASKED]"
            else:
                sanitized[key] = value
        
        return sanitized
    
    async def _make_request_with_retry(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> httpx.Response:
        """Make HTTP request with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json,
                    params=params,
                    **kwargs
                )
                
                # Log response
                logger.debug(
                    f"{method} {url} -> {response.status_code} "
                    f"({len(response.content)} bytes)"
                )
                
                # Don't retry on client errors (4xx), only server errors (5xx)
                if response.status_code < 500:
                    return response
                
                # Server error - retry if we have attempts left
                if attempt < self.max_retries:
                    wait_time = self.retry_backoff_factor ** attempt
                    logger.warning(
                        f"Server error {response.status_code}, retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                
                return response
                
            except (httpx.TimeoutException, asyncio.TimeoutError) as e:
                last_exception = TimeoutError(f"Request timed out after {self.timeout}s")
                if attempt < self.max_retries:
                    wait_time = self.retry_backoff_factor ** attempt
                    logger.warning(
                        f"Request timeout, retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    continue
            
            except (httpx.ConnectError, httpx.NetworkError) as e:
                last_exception = ConnectionError(f"Connection failed: {str(e)}")
                if attempt < self.max_retries:
                    wait_time = self.retry_backoff_factor ** attempt
                    logger.warning(
                        f"Connection error, retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{self.max_retries}): {str(e)}"
                    )
                    await asyncio.sleep(wait_time)
                    continue
        
        # All retries exhausted
        if last_exception:
            raise last_exception
        
        return response
    
    async def request(
        self,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make HTTP request to API endpoint.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            headers: Optional headers to include
            json: Optional JSON data to send
            params: Optional query parameters
            **kwargs: Additional arguments passed to httpx
            
        Returns:
            Response data as dictionary
            
        Raises:
            HTTPClientError: For HTTP errors
            RateLimitError: When rate limited
            TimeoutError: When request times out
            ConnectionError: When connection fails
        """
        # Apply rate limiting
        rate_limiter = self._get_rate_limiter(endpoint)
        await rate_limiter.acquire()
        
        # Build full URL
        url = self._build_url(endpoint)
        
        # Prepare headers
        request_headers = headers or {}
        
        # Log request (sanitized)
        log_data = {
            "method": method,
            "url": url,
            "headers": self._sanitize_for_logging(request_headers),
            "params": params,
        }
        if json:
            log_data["json"] = self._sanitize_for_logging(json)
        
        logger.debug(f"Making request: {log_data}")
        
        try:
            # Make request with retry logic
            response = await self._make_request_with_retry(
                method=method,
                url=url,
                headers=request_headers,
                json=json,
                params=params,
                **kwargs
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                retry_after_seconds = int(retry_after) if retry_after else 60
                
                raise RateLimitError(
                    message="Rate limit exceeded",
                    status_code=429,
                    retry_after=retry_after_seconds,
                    request_id=response.headers.get("X-Request-ID")
                )
            
            # Parse response
            try:
                response_data = response.json() if response.content else {}
            except Exception:
                response_data = {"content": response.text}
            
            # Handle HTTP errors
            if not response.is_success:
                error_message = response_data.get("message", f"HTTP {response.status_code}")
                
                raise create_http_error(
                    status_code=response.status_code,
                    message=error_message,
                    response_data=response_data,
                    request_id=response.headers.get("X-Request-ID")
                )
            
            return response_data
            
        except HTTPClientError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise HTTPClientError(f"Unexpected error: {str(e)}")
    
    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make GET request."""
        return await self.request("GET", endpoint, params=params, headers=headers, **kwargs)
    
    async def post(
        self,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make POST request."""
        return await self.request("POST", endpoint, json=json, headers=headers, **kwargs)
    
    async def put(
        self,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make PUT request."""
        return await self.request("PUT", endpoint, json=json, headers=headers, **kwargs)
    
    async def delete(
        self,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make DELETE request."""
        return await self.request("DELETE", endpoint, headers=headers, **kwargs)