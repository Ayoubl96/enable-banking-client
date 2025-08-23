import pytest
from datetime import datetime, timezone, timedelta, date
from unittest.mock import AsyncMock, patch
from decimal import Decimal

from enable_banking.operations.auth_operations import AuthOperations
from enable_banking.operations.account_operations import AccountOperations
from enable_banking.session.models import Session, Account, ASPSP
from enable_banking.models.responses import (
    ApplicationInfo, AuthResponse, BalanceResponse, TransactionResponse,
    Amount, Balance, Transaction
)
from enable_banking.client.exceptions import NotFoundError, AuthorizationError


@pytest.fixture
def mock_http_client():
    """Mock HTTP client."""
    return AsyncMock()


@pytest.fixture
def mock_jwt_manager():
    """Mock JWT manager."""
    manager = AsyncMock()
    manager.get_authorization_header.return_value = {"Authorization": "Bearer test_token"}
    return manager


@pytest.fixture
def mock_session_manager():
    """Mock session manager."""
    return AsyncMock()


@pytest.fixture
def sample_session():
    """Create sample session."""
    aspsp = ASPSP(name="Test Bank", country="US")
    accounts = [
        Account(
            uid="acc123",
            iban="US12345678901234567890",
            name="Checking Account",
            currency="USD",
        )
    ]
    
    return Session(
        session_id="session123",
        authorization_id="auth123",
        psu_id_hash="psu_hash",
        accounts=accounts,
        aspsp=aspsp,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


@pytest.fixture
def auth_operations(mock_http_client, mock_jwt_manager, mock_session_manager):
    """Create AuthOperations instance."""
    return AuthOperations(
        http_client=mock_http_client,
        jwt_manager=mock_jwt_manager,
        session_manager=mock_session_manager,
    )


@pytest.fixture  
def account_operations(mock_http_client, mock_jwt_manager, mock_session_manager):
    """Create AccountOperations instance."""
    return AccountOperations(
        http_client=mock_http_client,
        jwt_manager=mock_jwt_manager,
        session_manager=mock_session_manager,
    )


class TestAuthOperations:
    
    @pytest.mark.asyncio
    async def test_get_application_info(self, auth_operations, mock_http_client):
        """Test getting application info."""
        # Mock response
        mock_response = {
            "application_id": "app123",
            "name": "Test App",
            "status": "active",
            "created_at": "2023-01-01T00:00:00Z",
            "permissions": ["account_info", "transactions"],
        }
        mock_http_client.get.return_value = mock_response
        
        # Call method
        result = await auth_operations.get_application_info()
        
        # Verify
        assert isinstance(result, ApplicationInfo)
        assert result.application_id == "app123"
        assert result.name == "Test App"
        assert result.status == "active"
        assert len(result.permissions) == 2
        
        mock_http_client.get.assert_called_once_with(
            "/application",
            headers={"Authorization": "Bearer test_token"}
        )
    
    @pytest.mark.asyncio
    async def test_start_authorization(self, auth_operations, mock_http_client):
        """Test starting authorization."""
        # Mock response
        mock_response = {
            "authorization_id": "auth123",
            "auth_url": "https://bank.com/auth?code=123",
            "expires_at": "2023-01-01T01:00:00Z",
            "state": "test_state",
        }
        mock_http_client.post.return_value = mock_response
        
        # Call method
        result = await auth_operations.start_authorization(
            aspsp_name="Test Bank",
            country="US",
            redirect_uri="https://app.com/callback",
            state="test_state",
        )
        
        # Verify
        assert isinstance(result, AuthResponse)
        assert result.authorization_id == "auth123"
        assert result.auth_url == "https://bank.com/auth?code=123"
        assert result.state == "test_state"
        
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert "/auth" in call_args[0]
        assert call_args[1]["json"]["aspsp"] == "Test Bank"
        assert call_args[1]["json"]["country"] == "US"
    
    @pytest.mark.asyncio
    async def test_create_session(
        self,
        auth_operations,
        mock_http_client,
        mock_session_manager,
        sample_session
    ):
        """Test creating session from authorization code."""
        # Mock API response
        mock_api_response = {
            "session_id": "api_session123",
            "authorization_id": "auth123",
            "psu_id": "user123",
            "accounts": [
                {
                    "uid": "acc123",
                    "iban": "US12345678901234567890",
                    "name": "Checking Account",
                    "currency": "USD",
                }
            ],
            "aspsp": {"name": "Test Bank", "country": "US"},
            "expires_at": "2023-01-01T01:00:00Z",
            "created_at": "2023-01-01T00:00:00Z",
        }
        mock_http_client.post.return_value = mock_api_response
        
        # Mock session manager
        mock_session_manager.create_session.return_value = sample_session
        
        # Call method
        result = await auth_operations.create_session(
            code="auth_code123",
            state="test_state",
            psu_id="user123",
        )
        
        # Verify
        assert result == sample_session
        mock_http_client.post.assert_called_once()
        mock_session_manager.create_session.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_session(self, auth_operations, mock_session_manager, sample_session):
        """Test getting existing session."""
        # Mock session manager
        mock_session_manager.get_session.return_value = sample_session
        
        # Call method
        result = await auth_operations.get_session("session123")
        
        # Verify
        assert result == sample_session
        mock_session_manager.get_session.assert_called_once_with("session123")
    
    @pytest.mark.asyncio
    async def test_delete_session(self, auth_operations, mock_session_manager):
        """Test deleting session."""
        # Mock session manager
        mock_session_manager.delete_session.return_value = True
        
        # Call method
        result = await auth_operations.delete_session("session123")
        
        # Verify
        assert result is True
        mock_session_manager.delete_session.assert_called_once_with("session123")


class TestAccountOperations:
    
    @pytest.mark.asyncio
    async def test_get_account_balances(
        self,
        account_operations,
        mock_http_client,
        mock_session_manager,
        sample_session,
    ):
        """Test getting account balances."""
        # Mock session manager
        mock_session_manager.get_session.return_value = sample_session
        
        # Mock API response
        mock_response = {
            "account_uid": "acc123",
            "balances": [
                {
                    "balance_type": "available",
                    "amount": {"value": "1000.00", "currency": "USD"},
                    "reference_date": "2023-01-01",
                }
            ],
            "updated_at": "2023-01-01T00:00:00Z",
        }
        mock_http_client.get.return_value = mock_response
        
        # Call method
        result = await account_operations.get_account_balances(
            session_id="session123",
            account_uid="acc123",
        )
        
        # Verify
        assert isinstance(result, BalanceResponse)
        assert result.account_uid == "acc123"
        assert len(result.balances) == 1
        assert result.balances[0].amount.value == Decimal("1000.00")
        assert result.balances[0].amount.currency == "USD"
        
        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        assert "/accounts/acc123/balances" in call_args[0]
        assert call_args[1]["headers"]["Session-ID"] == "session123"
    
    @pytest.mark.asyncio
    async def test_get_account_transactions(
        self,
        account_operations,
        mock_http_client,
        mock_session_manager,
        sample_session,
    ):
        """Test getting account transactions."""
        # Mock session manager
        mock_session_manager.get_session.return_value = sample_session
        
        # Mock API response
        mock_response = {
            "account_uid": "acc123",
            "transactions": [
                {
                    "transaction_id": "txn123",
                    "booking_date": "2023-01-01",
                    "value_date": "2023-01-01",
                    "transaction_amount": {"value": "-50.00", "currency": "USD"},
                    "creditor_name": "Test Merchant",
                    "booking_status": "booked",
                }
            ],
            "total_count": 1,
            "has_more": False,
            "updated_at": "2023-01-01T00:00:00Z",
        }
        mock_http_client.get.return_value = mock_response
        
        # Call method
        result = await account_operations.get_account_transactions(
            session_id="session123",
            account_uid="acc123",
            date_from=date(2023, 1, 1),
            date_to=date(2023, 1, 31),
            limit=50,
        )
        
        # Verify
        assert isinstance(result, TransactionResponse)
        assert result.account_uid == "acc123"
        assert len(result.transactions) == 1
        assert result.transactions[0].transaction_id == "txn123"
        assert result.transactions[0].transaction_amount.value == Decimal("-50.00")
        
        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        assert "/accounts/acc123/transactions" in call_args[0]
        assert "date_from" in call_args[1]["params"]
        assert "date_to" in call_args[1]["params"]
        assert call_args[1]["params"]["limit"] == 50
    
    @pytest.mark.asyncio
    async def test_get_session_accounts(
        self,
        account_operations,
        mock_session_manager,
        sample_session,
    ):
        """Test getting session accounts."""
        # Mock session manager
        mock_session_manager.get_session.return_value = sample_session
        
        # Call method
        result = await account_operations.get_session_accounts("session123")
        
        # Verify
        assert result == sample_session.accounts
        assert len(result) == 1
        assert result[0].uid == "acc123"
        
        mock_session_manager.get_session.assert_called_once_with("session123")
    
    @pytest.mark.asyncio
    async def test_get_account_details(
        self,
        account_operations,
        mock_session_manager,
        sample_session,
    ):
        """Test getting account details."""
        # Mock session manager
        mock_session_manager.get_session.return_value = sample_session
        
        # Call method
        result = await account_operations.get_account_details(
            session_id="session123",
            account_uid="acc123",
        )
        
        # Verify
        assert isinstance(result, Account)
        assert result.uid == "acc123"
        assert result.name == "Checking Account"
        assert result.currency == "USD"
    
    @pytest.mark.asyncio
    async def test_account_not_authorized(
        self,
        account_operations,
        mock_session_manager,
        sample_session,
    ):
        """Test accessing unauthorized account."""
        # Mock session manager
        mock_session_manager.get_session.return_value = sample_session
        
        # Call method with non-existent account
        with pytest.raises(AuthorizationError):
            await account_operations.get_account_balances(
                session_id="session123",
                account_uid="unauthorized_account",
            )
    
    @pytest.mark.asyncio
    async def test_session_not_found(
        self,
        account_operations,
        mock_session_manager,
    ):
        """Test accessing non-existent session."""
        # Mock session manager to return None
        mock_session_manager.get_session.return_value = None
        
        # Call method
        with pytest.raises(NotFoundError):
            await account_operations.get_account_balances(
                session_id="nonexistent_session",
                account_uid="acc123",
            )