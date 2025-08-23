import pytest
import jwt
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from ..enable_banking.auth.jwt_manager import JWTManager, JWTAuthenticationError


@pytest.fixture
def test_private_key():
    """Generate a test RSA private key."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    return private_key


@pytest.fixture
def test_private_key_pem(test_private_key):
    """Get PEM encoded private key."""
    return test_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )


@pytest.fixture
def temp_key_file(test_private_key_pem):
    """Create a temporary private key file."""
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as f:
        f.write(test_private_key_pem)
        temp_path = f.name

    yield temp_path

    # Cleanup
    os.unlink(temp_path)


@pytest.fixture
def jwt_manager(temp_key_file):
    """Create a JWT manager instance for testing."""
    # Set environment variables for testing
    os.environ["TESTING"] = "true"
    os.environ["ENABLE_BANKING_APPLICATION_ID"] = "test_app_id"

    manager = JWTManager(
        private_key_path=temp_key_file,
        application_id="test_app_id",
        audience="https://api.test.com",
        token_expiry_minutes=5
    )

    yield manager

    # Cleanup
    if "TESTING" in os.environ:
        del os.environ["TESTING"]
    if "ENABLE_BANKING_APPLICATION_ID" in os.environ:
        del os.environ["ENABLE_BANKING_APPLICATION_ID"]


class TestJWTManager:

    def test_initialization(self, jwt_manager):
        """Test JWT manager initialization."""
        assert jwt_manager.application_id == "test_app_id"
        assert jwt_manager.audience == "https://api.test.com"
        assert jwt_manager.algorithm == "RS256"
        assert jwt_manager.token_expiry_minutes == 5
        assert jwt_manager._private_key is not None

    def test_missing_private_key_file(self):
        """Test error when private key file doesn't exist."""
        os.environ["TESTING"] = "true"

        with pytest.raises(JWTAuthenticationError, match="Private key file not found"):
            JWTManager(
                private_key_path="/nonexistent/path/key.pem",
                application_id="test_app_id"
            )

        if "TESTING" in os.environ:
            del os.environ["TESTING"]

    def test_generate_token(self, jwt_manager):
        """Test JWT token generation."""
        token = jwt_manager.generate_token()

        assert isinstance(token, str)
        assert len(token.split('.')) == 3  # JWT has 3 parts

        # Decode token to verify structure
        public_key = jwt_manager._private_key.public_key()
        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        decoded = jwt.decode(
            token,
            public_key_pem,
            algorithms=["RS256"],
            audience="https://api.test.com"
        )

        assert decoded["iss"] == "test_app_id"
        assert decoded["sub"] == "test_app_id"
        assert decoded["aud"] == "https://api.test.com"
        assert "iat" in decoded
        assert "exp" in decoded

    def test_token_caching(self, jwt_manager):
        """Test that tokens are cached and reused."""
        token1 = jwt_manager.generate_token()
        token2 = jwt_manager.generate_token()

        assert token1 == token2

    def test_force_refresh(self, jwt_manager):
        """Test force refresh of token."""
        token1 = jwt_manager.generate_token()
        token2 = jwt_manager.generate_token(force_refresh=True)

        assert token1 != token2

    def test_token_validation(self, jwt_manager):
        """Test token validation."""
        token = jwt_manager.generate_token()
        decoded = jwt_manager.validate_token(token)

        assert decoded["iss"] == "test_app_id"
        assert decoded["sub"] == "test_app_id"
        assert decoded["aud"] == "https://api.test.com"

    def test_invalid_token_validation(self, jwt_manager):
        """Test validation of invalid token."""
        with pytest.raises(JWTAuthenticationError, match="Invalid token"):
            jwt_manager.validate_token("invalid.token.here")

    def test_get_token_info(self, jwt_manager):
        """Test getting token information."""
        # No token initially
        info = jwt_manager.get_token_info()
        assert info["status"] == "no_token"
        assert info["token"] is None

        # After generating token
        token = jwt_manager.generate_token()
        info = jwt_manager.get_token_info()

        assert info["status"] == "valid"
        assert info["token"] == token
        assert info["application_id"] == "test_app_id"
        assert info["expires_at"] is not None

    def test_authorization_header(self, jwt_manager):
        """Test getting authorization header."""
        header = jwt_manager.get_authorization_header()

        assert "Authorization" in header
        assert header["Authorization"].startswith("Bearer ")

        # Extract and validate token
        token = header["Authorization"].replace("Bearer ", "")
        decoded = jwt_manager.validate_token(token)
        assert decoded["iss"] == "test_app_id"

    def test_refresh_token(self, jwt_manager):
        """Test token refresh."""
        token1 = jwt_manager.generate_token()
        token2 = jwt_manager.refresh_token()

        assert token1 != token2

        # Both tokens should be valid
        jwt_manager.validate_token(token1)
        jwt_manager.validate_token(token2)
