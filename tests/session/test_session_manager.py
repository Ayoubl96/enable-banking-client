import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from enable_banking.session.session_manager import SessionManager
from enable_banking.session.models import Session, Account, ASPSP


@pytest.fixture
def sample_aspsp():
    """Create sample ASPSP data."""
    return ASPSP(
        name="Test Bank",
        country="US",
        bic="TESTUS33",
    )


@pytest.fixture
def sample_accounts():
    """Create sample account data."""
    return [
        Account(
            uid="acc123",
            iban="US12345678901234567890",
            name="Checking Account",
            currency="USD",
            account_type="checking",
        ),
        Account(
            uid="acc456",
            iban="US09876543210987654321",
            name="Savings Account",
            currency="USD",
            account_type="savings",
        ),
    ]


@pytest.fixture
async def session_manager():
    """Create session manager for testing."""
    manager = SessionManager(
        redis_url=None,  # Disable Redis for tests
        default_session_ttl=3600,
        cleanup_interval=60,
    )
    await manager.start()
    yield manager
    await manager.stop()


@pytest.fixture
async def sample_session(session_manager, sample_aspsp, sample_accounts):
    """Create a sample session."""
    return await session_manager.create_session(
        authorization_id="auth123",
        psu_id="user123",
        aspsp=sample_aspsp,
        accounts=sample_accounts,
    )


class TestSessionModels:
    
    def test_account_model(self):
        """Test Account model."""
        account = Account(
            uid="test123",
            iban="US12345678901234567890",
            name="Test Account",
            currency="USD",
        )
        
        assert account.uid == "test123"
        assert account.iban == "US12345678901234567890"
        assert account.name == "Test Account"
        assert account.currency == "USD"
    
    def test_aspsp_model(self):
        """Test ASPSP model."""
        aspsp = ASPSP(
            name="Test Bank",
            country="US",
            bic="TESTUS33",
        )
        
        assert aspsp.name == "Test Bank"
        assert aspsp.country == "US"
        assert aspsp.bic == "TESTUS33"
    
    def test_session_model(self, sample_aspsp, sample_accounts):
        """Test Session model."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        session = Session(
            authorization_id="auth123",
            psu_id_hash="hashed_psu_id",
            accounts=sample_accounts,
            aspsp=sample_aspsp,
            expires_at=expires_at,
        )
        
        assert session.authorization_id == "auth123"
        assert session.psu_id_hash == "hashed_psu_id"
        assert len(session.accounts) == 2
        assert session.aspsp.name == "Test Bank"
        assert not session.is_expired
        assert session.time_until_expiry > 0
    
    def test_session_expiration(self, sample_aspsp, sample_accounts):
        """Test session expiration logic."""
        # Create expired session
        expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        
        session = Session(
            authorization_id="auth123",
            psu_id_hash="hashed_psu_id",
            accounts=sample_accounts,
            aspsp=sample_aspsp,
            expires_at=expires_at,
        )
        
        assert session.is_expired
        assert session.time_until_expiry == 0
    
    def test_session_account_operations(self, sample_aspsp, sample_accounts):
        """Test session account operations."""
        session = Session(
            authorization_id="auth123",
            psu_id_hash="hashed_psu_id",
            accounts=[],
            aspsp=sample_aspsp,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        
        # Add accounts
        for account in sample_accounts:
            session.add_account(account)
        
        assert len(session.accounts) == 2
        
        # Test getting account
        account = session.get_account("acc123")
        assert account is not None
        assert account.uid == "acc123"
        
        # Test non-existent account
        account = session.get_account("nonexistent")
        assert account is None
    
    def test_session_serialization(self, sample_aspsp, sample_accounts):
        """Test session to/from dict conversion."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        original_session = Session(
            authorization_id="auth123",
            psu_id_hash="hashed_psu_id",
            accounts=sample_accounts,
            aspsp=sample_aspsp,
            expires_at=expires_at,
            metadata={"test": "value"},
        )
        
        # Convert to dict and back
        session_dict = original_session.to_dict()
        restored_session = Session.from_dict(session_dict)
        
        assert restored_session.authorization_id == original_session.authorization_id
        assert restored_session.psu_id_hash == original_session.psu_id_hash
        assert len(restored_session.accounts) == len(original_session.accounts)
        assert restored_session.aspsp.name == original_session.aspsp.name
        assert restored_session.metadata == original_session.metadata


class TestSessionManager:
    
    @pytest.mark.asyncio
    async def test_session_manager_initialization(self):
        """Test session manager initialization."""
        manager = SessionManager(
            redis_url=None,
            default_session_ttl=1800,
            cleanup_interval=120,
        )
        
        assert manager.default_session_ttl == 1800
        assert manager.cleanup_interval == 120
        assert manager._redis is None
    
    @pytest.mark.asyncio
    async def test_create_session(self, session_manager, sample_aspsp, sample_accounts):
        """Test session creation."""
        session = await session_manager.create_session(
            authorization_id="auth123",
            psu_id="user123",
            aspsp=sample_aspsp,
            accounts=sample_accounts,
        )
        
        assert session.authorization_id == "auth123"
        assert session.psu_id_hash != "user123"  # Should be hashed
        assert len(session.accounts) == 2
        assert session.aspsp.name == "Test Bank"
        assert not session.is_expired
    
    @pytest.mark.asyncio
    async def test_get_session(self, session_manager, sample_session):
        """Test getting session by ID."""
        # Get existing session
        retrieved_session = await session_manager.get_session(sample_session.session_id)
        
        assert retrieved_session is not None
        assert retrieved_session.session_id == sample_session.session_id
        assert retrieved_session.authorization_id == sample_session.authorization_id
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, session_manager):
        """Test getting non-existent session."""
        session = await session_manager.get_session("nonexistent")
        assert session is None
    
    @pytest.mark.asyncio
    async def test_delete_session(self, session_manager, sample_session):
        """Test session deletion."""
        session_id = sample_session.session_id
        
        # Verify session exists
        session = await session_manager.get_session(session_id)
        assert session is not None
        
        # Delete session
        deleted = await session_manager.delete_session(session_id)
        assert deleted is True
        
        # Verify session is gone
        session = await session_manager.get_session(session_id)
        assert session is None
        
        # Try to delete again
        deleted = await session_manager.delete_session(session_id)
        assert deleted is False
    
    @pytest.mark.asyncio
    async def test_list_sessions(self, session_manager, sample_aspsp, sample_accounts):
        """Test listing sessions."""
        # Create multiple sessions
        session1 = await session_manager.create_session(
            authorization_id="auth1",
            psu_id="user1",
            aspsp=sample_aspsp,
            accounts=sample_accounts,
        )
        
        different_aspsp = ASPSP(name="Other Bank", country="CA")
        session2 = await session_manager.create_session(
            authorization_id="auth2",
            psu_id="user2",
            aspsp=different_aspsp,
            accounts=sample_accounts,
        )
        
        # List all sessions
        sessions = await session_manager.list_sessions()
        assert len(sessions) == 2
        
        # List sessions for specific bank
        test_bank_sessions = await session_manager.list_sessions(aspsp_name="Test Bank")
        assert len(test_bank_sessions) == 1
        assert test_bank_sessions[0].aspsp.name == "Test Bank"
    
    @pytest.mark.asyncio
    async def test_get_sessions_by_bank(self, session_manager, sample_aspsp, sample_accounts):
        """Test getting sessions by bank."""
        await session_manager.create_session(
            authorization_id="auth1",
            psu_id="user1",
            aspsp=sample_aspsp,
            accounts=sample_accounts,
        )
        
        sessions = await session_manager.get_sessions_by_bank("Test Bank")
        assert len(sessions) == 1
        assert sessions[0].aspsp.name == "Test Bank"
        
        # Test non-existent bank
        sessions = await session_manager.get_sessions_by_bank("Non-existent Bank")
        assert len(sessions) == 0
    
    @pytest.mark.asyncio
    async def test_extend_session(self, session_manager, sample_session):
        """Test extending session expiration."""
        original_expiry = sample_session.expires_at
        
        # Extend session by 1 hour
        extended_session = await session_manager.extend_session(
            sample_session.session_id, 3600
        )
        
        assert extended_session is not None
        assert extended_session.expires_at > original_expiry
        assert (extended_session.expires_at - original_expiry).total_seconds() == 3600
    
    @pytest.mark.asyncio
    async def test_extend_nonexistent_session(self, session_manager):
        """Test extending non-existent session."""
        result = await session_manager.extend_session("nonexistent", 3600)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_session_stats(self, session_manager, sample_aspsp, sample_accounts):
        """Test getting session statistics."""
        # Create active sessions
        await session_manager.create_session(
            authorization_id="auth1",
            psu_id="user1",
            aspsp=sample_aspsp,
            accounts=sample_accounts,
        )
        
        await session_manager.create_session(
            authorization_id="auth2",
            psu_id="user2",
            aspsp=sample_aspsp,
            accounts=sample_accounts,
        )
        
        # Create expired session
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session_manager.create_session(
            authorization_id="auth3",
            psu_id="user3",
            aspsp=sample_aspsp,
            accounts=sample_accounts,
            expires_at=expired_time,
        )
        
        stats = await session_manager.get_session_stats()
        
        assert stats["total_sessions"] == 3
        assert stats["active_sessions"] == 2
        assert stats["expired_sessions"] == 1
        assert stats["unique_banks"] == 1
        assert stats["redis_enabled"] is False
    
    @pytest.mark.asyncio
    async def test_expired_session_cleanup(self, session_manager, sample_session):
        """Test that expired sessions are not returned."""
        # Manually set session as expired
        sample_session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        
        # Store the expired session
        await session_manager._store_session(sample_session)
        
        # Try to get expired session
        retrieved_session = await session_manager.get_session(sample_session.session_id)
        assert retrieved_session is None
    
    @pytest.mark.asyncio
    async def test_context_manager(self, sample_aspsp, sample_accounts):
        """Test session manager as context manager."""
        async with SessionManager() as manager:
            session = await manager.create_session(
                authorization_id="auth123",
                psu_id="user123",
                aspsp=sample_aspsp,
                accounts=sample_accounts,
            )
            
            assert session is not None
            
        # Manager should be stopped after context