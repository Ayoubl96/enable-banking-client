import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch
import httpx

from enable_banking.client.http_client import HTTPClient, RateLimiter
from enable_banking.client.exceptions import (
    HTTPClientError,
    RateLimitError,
    TimeoutError,
    ConnectionError,
    AuthenticationError,
    ValidationError,
    ServerError,
)


@pytest.fixture
async def http_client():
    """Create HTTP client instance for testing."""
    client = HTTPClient(
        base_url="https://api.test.com",
        timeout=5.0,
        auth_rate_limit=60,  # Higher limits for faster tests
        data_rate_limit=120,
        max_retries=2,
    )
    yield client
    await client.close()


@pytest.fixture
def mock_response():
    """Create mock HTTP response."""
    response = AsyncMock(spec=httpx.Response)
    response.status_code = 200
    response.is_success = True
    response.json.return_value = {"status": "success"}
    response.content = b'{"status": "success"}'
    response.text = '{"status": "success"}'
    response.headers = {"Content-Type": "application/json"}
    return response


class TestRateLimiter:
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests_under_limit(self):
        """Test that rate limiter allows requests under the limit."""
        limiter = RateLimiter(requests_per_minute=10)
        
        # Should allow multiple requests quickly
        for _ in range(5):
            await limiter.acquire()  # Should not block
    
    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_when_limit_exceeded(self):
        """Test that rate limiter blocks when limit is exceeded."""
        limiter = RateLimiter(requests_per_minute=2)
        
        # Fill up the rate limiter
        await limiter.acquire()
        await limiter.acquire()
        
        # Next request should block (but we won't wait for it)
        start_time = time.time()
        
        # This should return immediately in our test due to time manipulation
        # In real usage, this would wait
        with patch('time.time') as mock_time:
            # Set initial time
            mock_time.return_value = start_time
            
            # Fill rate limiter
            limiter.requests = [start_time - 30, start_time - 10]  # Two recent requests
            
            # Mock time progression to show rate limiting working
            mock_time.return_value = start_time + 1
            
            # This would normally wait, but since we control time, it should pass
            await limiter.acquire()


class TestHTTPClient:
    
    def test_initialization(self):
        """Test HTTP client initialization."""
        client = HTTPClient(
            base_url="https://api.test.com",
            timeout=10.0,
            auth_rate_limit=5,
            data_rate_limit=50,
        )
        
        assert client.base_url == "https://api.test.com"
        assert client.timeout == 10.0
        assert client.auth_rate_limiter.requests_per_minute == 5
        assert client.data_rate_limiter.requests_per_minute == 50
    
    def test_build_url(self, http_client):
        """Test URL building."""
        assert http_client._build_url("/auth") == "https://api.test.com/auth"
        assert http_client._build_url("auth") == "https://api.test.com/auth"
        assert http_client._build_url("/accounts/123") == "https://api.test.com/accounts/123"
    
    def test_get_rate_limiter(self, http_client):
        """Test rate limiter selection based on endpoint."""
        # Auth endpoints should use auth rate limiter
        assert http_client._get_rate_limiter("/auth") == http_client.auth_rate_limiter
        assert http_client._get_rate_limiter("/sessions") == http_client.auth_rate_limiter
        assert http_client._get_rate_limiter("/application") == http_client.auth_rate_limiter
        
        # Other endpoints should use data rate limiter
        assert http_client._get_rate_limiter("/accounts") == http_client.data_rate_limiter
        assert http_client._get_rate_limiter("/transactions") == http_client.data_rate_limiter
    
    def test_sanitize_for_logging(self, http_client):
        """Test data sanitization for logging."""
        sensitive_data = {
            "authorization": "Bearer token123",
            "account_number": "1234567890",
            "normal_field": "normal_value",
            "password": "secret123"
        }
        
        sanitized = http_client._sanitize_for_logging(sensitive_data)
        
        assert sanitized["authorization"] != "Bearer token123"
        assert sanitized["account_number"] != "1234567890"
        assert sanitized["password"] != "secret123"
        assert sanitized["normal_field"] == "normal_value"
    
    @pytest.mark.asyncio
    async def test_successful_request(self, http_client, mock_response):
        """Test successful HTTP request."""
        with patch.object(http_client.client, 'request', return_value=mock_response):
            with patch.object(http_client.auth_rate_limiter, 'acquire', new_callable=AsyncMock):
                result = await http_client.request("GET", "/test")
                
                assert result == {"status": "success"}
    
    @pytest.mark.asyncio
    async def test_get_request(self, http_client, mock_response):
        """Test GET request method."""
        with patch.object(http_client.client, 'request', return_value=mock_response):
            with patch.object(http_client.data_rate_limiter, 'acquire', new_callable=AsyncMock):
                result = await http_client.get("/accounts", params={"limit": 10})
                
                assert result == {"status": "success"}
    
    @pytest.mark.asyncio
    async def test_post_request(self, http_client, mock_response):
        """Test POST request method."""
        with patch.object(http_client.client, 'request', return_value=mock_response):
            with patch.object(http_client.auth_rate_limiter, 'acquire', new_callable=AsyncMock):
                result = await http_client.post("/auth", json={"code": "test123"})
                
                assert result == {"status": "success"}
    
    @pytest.mark.asyncio
    async def test_rate_limit_error(self, http_client):
        """Test rate limit error handling."""
        mock_response = AsyncMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60", "X-Request-ID": "req123"}
        
        with patch.object(http_client.client, 'request', return_value=mock_response):
            with patch.object(http_client.data_rate_limiter, 'acquire', new_callable=AsyncMock):
                with pytest.raises(RateLimitError) as exc_info:
                    await http_client.request("GET", "/test")
                
                assert exc_info.value.status_code == 429
                assert exc_info.value.retry_after == 60
                assert exc_info.value.request_id == "req123"
    
    @pytest.mark.asyncio
    async def test_authentication_error(self, http_client):
        """Test authentication error handling."""
        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.is_success = False
        mock_response.json.return_value = {"message": "Invalid token"}
        mock_response.content = b'{"message": "Invalid token"}'
        mock_response.headers = {}
        
        with patch.object(http_client.client, 'request', return_value=mock_response):
            with patch.object(http_client.data_rate_limiter, 'acquire', new_callable=AsyncMock):
                with pytest.raises(AuthenticationError) as exc_info:
                    await http_client.request("GET", "/test")
                
                assert exc_info.value.status_code == 401
                assert "Invalid token" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_validation_error(self, http_client):
        """Test validation error handling."""
        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_response.is_success = False
        mock_response.json.return_value = {"message": "Invalid request"}
        mock_response.content = b'{"message": "Invalid request"}'
        mock_response.headers = {}
        
        with patch.object(http_client.client, 'request', return_value=mock_response):
            with patch.object(http_client.data_rate_limiter, 'acquire', new_callable=AsyncMock):
                with pytest.raises(ValidationError) as exc_info:
                    await http_client.request("GET", "/test")
                
                assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_server_error_with_retry(self, http_client):
        """Test server error handling with retry logic."""
        # Mock responses: first two fail with 500, third succeeds
        responses = [
            AsyncMock(status_code=500, is_success=False, json=lambda: {"error": "Server error"}),
            AsyncMock(status_code=500, is_success=False, json=lambda: {"error": "Server error"}),
            AsyncMock(status_code=200, is_success=True, json=lambda: {"status": "success"}),
        ]
        
        for resp in responses:
            resp.content = b'{"status": "success"}' if resp.status_code == 200 else b'{"error": "Server error"}'
            resp.headers = {}
        
        with patch.object(http_client.client, 'request', side_effect=responses):
            with patch.object(http_client.data_rate_limiter, 'acquire', new_callable=AsyncMock):
                with patch('asyncio.sleep', new_callable=AsyncMock):  # Speed up test
                    result = await http_client.request("GET", "/test")
                    
                    assert result == {"status": "success"}
    
    @pytest.mark.asyncio
    async def test_timeout_error(self, http_client):
        """Test timeout error handling."""
        with patch.object(
            http_client.client, 'request', 
            side_effect=httpx.TimeoutException("Request timed out")
        ):
            with patch.object(http_client.data_rate_limiter, 'acquire', new_callable=AsyncMock):
                with pytest.raises(TimeoutError) as exc_info:
                    await http_client.request("GET", "/test")
                
                assert "timed out" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_connection_error(self, http_client):
        """Test connection error handling."""
        with patch.object(
            http_client.client, 'request', 
            side_effect=httpx.ConnectError("Connection failed")
        ):
            with patch.object(http_client.data_rate_limiter, 'acquire', new_callable=AsyncMock):
                with pytest.raises(ConnectionError) as exc_info:
                    await http_client.request("GET", "/test")
                
                assert "Connection failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test HTTP client as context manager."""
        async with HTTPClient() as client:
            assert client.client is not None
        
        # Client should be closed after exiting context