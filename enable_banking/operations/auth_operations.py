"""Authentication operations for Enable Banking API."""

from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from enable_banking.config.logging import get_logger
from enable_banking.client.http_client import HTTPClient
from enable_banking.auth.jwt_manager import JWTManager
from enable_banking.session.session_manager import SessionManager
from enable_banking.session.models import Session, Account, ASPSP
from enable_banking.models.requests import AuthRequest, SessionRequest
from enable_banking.models.responses import AuthResponse, SessionResponse, ApplicationInfo
from enable_banking.client.exceptions import HTTPClientError, ValidationError

logger = get_logger(__name__)


class AuthOperations:
    """Handle authentication and session operations with Enable Banking API."""
    
    def __init__(
        self,
        http_client: HTTPClient,
        jwt_manager: JWTManager,
        session_manager: SessionManager,
    ):
        """Initialize auth operations.
        
        Args:
            http_client: HTTP client for API requests
            jwt_manager: JWT manager for authentication
            session_manager: Session manager for session storage
        """
        self.http_client = http_client
        self.jwt_manager = jwt_manager
        self.session_manager = session_manager
        
        logger.debug("Auth operations initialized")
    
    async def get_application_info(self) -> ApplicationInfo:
        """Get application information.
        
        Returns:
            Application information
            
        Raises:
            HTTPClientError: For API errors
        """
        try:
            # Get authentication headers
            headers = self.jwt_manager.get_authorization_header()
            
            # Make API request
            response = await self.http_client.get("/application", headers=headers)
            
            logger.info("Retrieved application information")
            return ApplicationInfo(**response)
            
        except Exception as e:
            logger.error(f"Failed to get application info: {e}")
            raise
    
    async def start_authorization(
        self,
        aspsp_name: str,
        country: str,
        redirect_uri: str,
        state: Optional[str] = None,
        psu_id: Optional[str] = None,
        psu_ip_address: Optional[str] = None,
    ) -> AuthResponse:
        """Start bank authorization process.
        
        Args:
            aspsp_name: Bank name (ASPSP identifier)
            country: Bank country code (ISO 2-letter)
            redirect_uri: Redirect URI after authorization
            state: Optional state parameter for OAuth flow
            psu_id: Optional PSU identifier
            psu_ip_address: Optional PSU IP address
            
        Returns:
            Authorization response with auth URL
            
        Raises:
            ValidationError: For invalid request parameters
            HTTPClientError: For API errors
        """
        try:
            # Validate request
            request = AuthRequest(
                aspsp=aspsp_name,
                country=country,
                redirect_uri=redirect_uri,
                state=state,
                psu_id=psu_id,
                psu_ip_address=psu_ip_address,
            )
            
            # Get authentication headers
            headers = self.jwt_manager.get_authorization_header()
            
            # Add PSU IP address header if provided
            if psu_ip_address:
                headers["PSU-IP-Address"] = psu_ip_address
            
            # Make API request
            response = await self.http_client.post(
                "/auth",
                json=request.dict(exclude_none=True),
                headers=headers,
            )
            
            logger.info(f"Started authorization for {aspsp_name} in {country}")
            return AuthResponse(**response)
            
        except Exception as e:
            logger.error(f"Failed to start authorization: {e}")
            raise
    
    async def create_session(
        self,
        code: str,
        state: Optional[str] = None,
        psu_id: Optional[str] = None,
        psu_ip_address: Optional[str] = None,
    ) -> Session:
        """Create session from authorization code.
        
        Args:
            code: Authorization code from callback
            state: State parameter from OAuth flow
            psu_id: PSU identifier
            psu_ip_address: PSU IP address
            
        Returns:
            Created session
            
        Raises:
            ValidationError: For invalid request parameters
            HTTPClientError: For API errors
        """
        try:
            # Validate request
            request = SessionRequest(code=code, state=state)
            
            # Get authentication headers
            headers = self.jwt_manager.get_authorization_header()
            
            # Add PSU IP address header if provided
            if psu_ip_address:
                headers["PSU-IP-Address"] = psu_ip_address
            
            # Make API request
            response = await self.http_client.post(
                "/sessions",
                json=request.dict(exclude_none=True),
                headers=headers,
            )
            
            # Parse response
            session_response = SessionResponse(**response)
            
            # Convert to our session model
            accounts = [
                Account(**acc) for acc in session_response.accounts
            ]
            
            aspsp = ASPSP(**session_response.aspsp)
            
            # Calculate expiration time (default to 1 hour from now if not provided)
            expires_at = session_response.expires_at
            if not expires_at:
                expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            
            # Create session using session manager
            session = await self.session_manager.create_session(
                authorization_id=session_response.authorization_id,
                psu_id=psu_id or session_response.psu_id,
                aspsp=aspsp,
                accounts=accounts,
                expires_at=expires_at,
                metadata={
                    "original_session_id": session_response.session_id,
                    "created_from_code": True,
                }
            )
            
            logger.info(
                f"Session created: {session.session_id} for {aspsp.name} "
                f"({len(accounts)} accounts)"
            )
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get existing session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session if found and valid, None otherwise
        """
        try:
            session = await self.session_manager.get_session(session_id)
            
            if session:
                logger.debug(f"Retrieved session: {session_id}")
            else:
                logger.debug(f"Session not found or expired: {session_id}")
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            raise
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was deleted, False if not found
        """
        try:
            deleted = await self.session_manager.delete_session(session_id)
            
            if deleted:
                logger.info(f"Session deleted: {session_id}")
            else:
                logger.debug(f"Session not found for deletion: {session_id}")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            raise
    
    async def extend_session(
        self,
        session_id: str,
        additional_seconds: int = 3600,
    ) -> Optional[Session]:
        """Extend session expiration time.
        
        Args:
            session_id: Session identifier
            additional_seconds: Additional seconds to add (default: 1 hour)
            
        Returns:
            Extended session if found, None otherwise
        """
        try:
            session = await self.session_manager.extend_session(
                session_id, additional_seconds
            )
            
            if session:
                logger.info(f"Session extended: {session_id} by {additional_seconds}s")
            else:
                logger.debug(f"Session not found for extension: {session_id}")
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to extend session: {e}")
            raise
    
    async def list_sessions(
        self,
        include_expired: bool = False,
        aspsp_name: Optional[str] = None,
    ) -> list[Session]:
        """List sessions.
        
        Args:
            include_expired: Include expired sessions
            aspsp_name: Filter by bank name
            
        Returns:
            List of sessions
        """
        try:
            sessions = await self.session_manager.list_sessions(
                include_expired=include_expired,
                aspsp_name=aspsp_name,
            )
            
            logger.debug(f"Listed {len(sessions)} sessions")
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            raise