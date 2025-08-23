import jwt
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from enable_banking.config.logging import get_logger
from enable_banking.config.settings import settings

logger = get_logger(__name__)


class JWTAuthenticationError(Exception):
    """Exception raised for JWT authentication errors."""
    pass


class JWTManager:
    """Manages JWT token generation and validation for Enable Banking API."""
    
    def __init__(
        self,
        private_key_path: Optional[str | Path] = None,
        application_id: Optional[str] = None,
        audience: Optional[str] = None,
        algorithm: str = "RS256",
        token_expiry_minutes: Optional[int] = None,
        private_key_password: Optional[bytes] = None,
    ):
        """Initialize JWT Manager.
        
        Args:
            private_key_path: Path to the PEM private key file (defaults to env var)
            application_id: Your Enable Banking application ID (defaults to env var)
            audience: JWT audience (defaults to Enable Banking API URL from env var)
            algorithm: JWT signing algorithm (default: RS256)
            token_expiry_minutes: Token expiry time in minutes (defaults to env var)
            private_key_password: Password for encrypted private key (optional)
        """
        self.private_key_path = Path(
            private_key_path or settings.enable_banking_private_key_path
        )
        self.application_id = application_id or settings.enable_banking_application_id
        self.audience = audience or settings.enable_banking_base_url
        self.algorithm = algorithm
        self.token_expiry_minutes = (
            token_expiry_minutes or settings.enable_banking_token_expiry_minutes
        )
        self.private_key_password = private_key_password
        
        self._private_key = None
        self._current_token = None
        self._token_expires_at = None
        
        # Load private key on initialization
        self._load_private_key()
        
        logger.info(f"JWT Manager initialized for application: {application_id}")
    
    def _load_private_key(self) -> None:
        """Load the private key from PEM file."""
        try:
            if not self.private_key_path.exists():
                raise JWTAuthenticationError(
                    f"Private key file not found: {self.private_key_path}"
                )
            
            with open(self.private_key_path, "rb") as key_file:
                private_key_data = key_file.read()
            
            self._private_key = load_pem_private_key(
                private_key_data,
                password=self.private_key_password,
            )
            
            logger.debug(f"Private key loaded successfully from {self.private_key_path}")
            
        except Exception as e:
            raise JWTAuthenticationError(
                f"Failed to load private key from {self.private_key_path}: {str(e)}"
            )
    
    def _create_jwt_payload(self) -> Dict[str, Any]:
        """Create JWT payload with required claims."""
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(minutes=self.token_expiry_minutes)
        
        payload = {
            "iss": self.application_id,  # Issuer
            "sub": self.application_id,  # Subject  
            "aud": self.audience,        # Audience
            "iat": int(now.timestamp()), # Issued at
            "exp": int(expiry.timestamp()), # Expiry
        }
        
        return payload
    
    def generate_token(self, force_refresh: bool = False) -> str:
        """Generate a new JWT token or return cached token if still valid.
        
        Args:
            force_refresh: Force generation of new token even if current one is valid
            
        Returns:
            JWT token string
        """
        try:
            # Return cached token if it's still valid and not forcing refresh
            if not force_refresh and self._is_token_valid():
                logger.debug("Returning cached JWT token")
                return self._current_token
            
            # Generate new token
            payload = self._create_jwt_payload()
            
            # Convert private key to PEM format for jwt library
            private_key_pem = self._private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            token = jwt.encode(
                payload, 
                private_key_pem, 
                algorithm=self.algorithm,
                headers={"alg": self.algorithm, "typ": "JWT"}
            )
            
            # Cache token and expiry
            self._current_token = token
            self._token_expires_at = datetime.fromtimestamp(
                payload["exp"], tz=timezone.utc
            )
            
            logger.debug(f"New JWT token generated, expires at: {self._token_expires_at}")
            return token
            
        except Exception as e:
            raise JWTAuthenticationError(f"Failed to generate JWT token: {str(e)}")
    
    def _is_token_valid(self) -> bool:
        """Check if current token is valid and not expired."""
        if not self._current_token or not self._token_expires_at:
            return False
        
        # Add 5 minute buffer before expiry
        buffer_time = timedelta(minutes=5)
        now = datetime.now(timezone.utc)
        
        return now < (self._token_expires_at - buffer_time)
    
    def get_token_info(self) -> Dict[str, Any]:
        """Get information about current token."""
        if not self._current_token:
            return {"status": "no_token", "token": None, "expires_at": None}
        
        return {
            "status": "valid" if self._is_token_valid() else "expired",
            "token": self._current_token,
            "expires_at": self._token_expires_at.isoformat() if self._token_expires_at else None,
            "application_id": self.application_id,
        }
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate a JWT token and return decoded payload.
        
        Args:
            token: JWT token to validate
            
        Returns:
            Decoded token payload
        """
        try:
            # Get public key from private key for validation
            public_key = self._private_key.public_key()
            public_key_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            decoded = jwt.decode(
                token,
                public_key_pem,
                algorithms=[self.algorithm],
                audience=self.audience,
                options={"verify_signature": True, "verify_exp": True}
            )
            
            return decoded
            
        except jwt.ExpiredSignatureError:
            raise JWTAuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise JWTAuthenticationError(f"Invalid token: {str(e)}")
        except Exception as e:
            raise JWTAuthenticationError(f"Token validation failed: {str(e)}")
    
    def refresh_token(self) -> str:
        """Force refresh of JWT token."""
        logger.debug("Refreshing JWT token")
        return self.generate_token(force_refresh=True)
    
    def get_authorization_header(self) -> Dict[str, str]:
        """Get authorization header with current JWT token."""
        token = self.generate_token()
        return {"Authorization": f"Bearer {token}"}