"""Account operations for Enable Banking API."""

from typing import Optional, List
from datetime import date

from enable_banking.config.logging import get_logger
from enable_banking.client.http_client import HTTPClient
from enable_banking.auth.jwt_manager import JWTManager
from enable_banking.session.session_manager import SessionManager
from enable_banking.session.models import Session, Account
from enable_banking.models.requests import BalanceRequest, TransactionRequest, TransactionFilter
from enable_banking.models.responses import BalanceResponse, TransactionResponse
from enable_banking.client.exceptions import HTTPClientError, NotFoundError, AuthorizationError

logger = get_logger(__name__)


class AccountOperations:
    """Handle account data operations with Enable Banking API."""
    
    def __init__(
        self,
        http_client: HTTPClient,
        jwt_manager: JWTManager,
        session_manager: SessionManager,
    ):
        """Initialize account operations.
        
        Args:
            http_client: HTTP client for API requests
            jwt_manager: JWT manager for authentication
            session_manager: Session manager for session storage
        """
        self.http_client = http_client
        self.jwt_manager = jwt_manager
        self.session_manager = session_manager
        
        logger.debug("Account operations initialized")
    
    async def _get_session_and_account(
        self,
        session_id: str,
        account_uid: str,
    ) -> tuple[Session, Account]:
        """Get session and validate account access.
        
        Args:
            session_id: Session identifier
            account_uid: Account unique identifier
            
        Returns:
            Tuple of (session, account)
            
        Raises:
            NotFoundError: If session or account not found
            AuthorizationError: If account not authorized in session
        """
        # Get session
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise NotFoundError(f"Session not found: {session_id}")
        
        # Find account in session
        account = session.get_account(account_uid)
        if not account:
            raise AuthorizationError(
                f"Account {account_uid} not authorized in session {session_id}"
            )
        
        return session, account
    
    async def get_account_balances(
        self,
        session_id: str,
        account_uid: str,
        psu_ip_address: Optional[str] = None,
    ) -> BalanceResponse:
        """Get account balances.
        
        Args:
            session_id: Session identifier
            account_uid: Account unique identifier
            psu_ip_address: Optional PSU IP address
            
        Returns:
            Account balances
            
        Raises:
            NotFoundError: If session or account not found
            AuthorizationError: If account not authorized
            HTTPClientError: For API errors
        """
        try:
            # Validate session and account
            session, account = await self._get_session_and_account(session_id, account_uid)
            
            # Validate request
            request = BalanceRequest(account_uid=account_uid)
            
            # Get authentication headers
            headers = self.jwt_manager.get_authorization_header()
            
            # Add session headers
            headers["Session-ID"] = session_id
            
            # Add PSU IP address header if provided
            if psu_ip_address:
                headers["PSU-IP-Address"] = psu_ip_address
            
            # Make API request
            endpoint = f"/accounts/{account_uid}/balances"
            response = await self.http_client.get(endpoint, headers=headers)
            
            logger.info(f"Retrieved balances for account {account_uid}")
            return BalanceResponse(**response)
            
        except Exception as e:
            logger.error(f"Failed to get account balances: {e}")
            raise
    
    async def get_account_transactions(
        self,
        session_id: str,
        account_uid: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
        booking_status: Optional[str] = None,
        psu_ip_address: Optional[str] = None,
    ) -> TransactionResponse:
        """Get account transactions.
        
        Args:
            session_id: Session identifier
            account_uid: Account unique identifier
            date_from: Start date for transactions
            date_to: End date for transactions
            limit: Maximum number of transactions (1-1000)
            offset: Offset for pagination
            booking_status: Booking status filter
            psu_ip_address: Optional PSU IP address
            
        Returns:
            Account transactions
            
        Raises:
            NotFoundError: If session or account not found
            AuthorizationError: If account not authorized
            HTTPClientError: For API errors
        """
        try:
            # Validate session and account
            session, account = await self._get_session_and_account(session_id, account_uid)
            
            # Create transaction filter
            filters = TransactionFilter(
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                offset=offset,
                booking_status=booking_status,
            )
            
            # Validate request
            request = TransactionRequest(account_uid=account_uid, filters=filters)
            
            # Get authentication headers
            headers = self.jwt_manager.get_authorization_header()
            
            # Add session headers
            headers["Session-ID"] = session_id
            
            # Add PSU IP address header if provided
            if psu_ip_address:
                headers["PSU-IP-Address"] = psu_ip_address
            
            # Make API request with query parameters
            endpoint = f"/accounts/{account_uid}/transactions"
            params = request.to_query_params()
            
            response = await self.http_client.get(
                endpoint,
                params=params,
                headers=headers,
            )
            
            logger.info(
                f"Retrieved transactions for account {account_uid} "
                f"(limit: {limit}, offset: {offset})"
            )
            
            return TransactionResponse(**response)
            
        except Exception as e:
            logger.error(f"Failed to get account transactions: {e}")
            raise
    
    async def get_session_accounts(self, session_id: str) -> List[Account]:
        """Get all accounts from session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of accounts in the session
            
        Raises:
            NotFoundError: If session not found
        """
        try:
            # Get session
            session = await self.session_manager.get_session(session_id)
            if not session:
                raise NotFoundError(f"Session not found: {session_id}")
            
            logger.debug(f"Retrieved {len(session.accounts)} accounts from session {session_id}")
            return session.accounts
            
        except Exception as e:
            logger.error(f"Failed to get session accounts: {e}")
            raise
    
    async def get_account_details(
        self,
        session_id: str,
        account_uid: str,
    ) -> Account:
        """Get account details from session.
        
        Args:
            session_id: Session identifier  
            account_uid: Account unique identifier
            
        Returns:
            Account details
            
        Raises:
            NotFoundError: If session or account not found
        """
        try:
            # Validate session and account
            session, account = await self._get_session_and_account(session_id, account_uid)
            
            logger.debug(f"Retrieved account details: {account_uid}")
            return account
            
        except Exception as e:
            logger.error(f"Failed to get account details: {e}")
            raise