import asyncio
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from threading import Lock
import redis.asyncio as redis

from enable_banking.config.logging import get_logger
from enable_banking.config.settings import settings
from enable_banking.session.models import Session, Account, ASPSP

logger = get_logger(__name__)


class SessionManager:
    """Manages bank authorization sessions in memory with optional Redis support."""
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_session_ttl: int = 3600,  # 1 hour
        cleanup_interval: int = 300,  # 5 minutes
    ):
        """Initialize session manager.
        
        Args:
            redis_url: Optional Redis URL for persistent storage and scaling
            default_session_ttl: Default session TTL in seconds
            cleanup_interval: Interval for cleanup task in seconds
        """
        self.redis_url = redis_url or settings.redis_url
        self.default_session_ttl = default_session_ttl
        self.cleanup_interval = cleanup_interval
        
        # In-memory session storage
        self._sessions: Dict[str, Session] = {}
        self._sessions_lock = Lock()
        
        # Redis client for scaling
        self._redis: Optional[redis.Redis] = None
        
        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.info(f"Session manager initialized (Redis: {'enabled' if self.redis_url else 'disabled'})")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
    
    async def start(self):
        """Start the session manager."""
        # Initialize Redis if URL provided
        if self.redis_url:
            try:
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                await self._redis.ping()  # Test connection
                logger.info("Redis connection established")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using in-memory storage only.")
                self._redis = None
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
        logger.info("Session manager started")
    
    async def stop(self):
        """Stop the session manager."""
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close Redis connection
        if self._redis:
            await self._redis.close()
            logger.info("Redis connection closed")
        
        logger.info("Session manager stopped")
    
    def _hash_psu_id(self, psu_id: str) -> str:
        """Hash PSU ID for privacy."""
        return hashlib.sha256(psu_id.encode()).hexdigest()[:16]
    
    def _get_redis_key(self, session_id: str) -> str:
        """Get Redis key for session."""
        return f"session:{session_id}"
    
    async def create_session(
        self,
        authorization_id: str,
        psu_id: str,
        aspsp: ASPSP,
        accounts: List[Account],
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Session:
        """Create a new session.
        
        Args:
            authorization_id: Authorization ID from Enable Banking
            psu_id: PSU (Payment Service User) identifier
            aspsp: Bank information
            accounts: List of authorized accounts
            expires_at: Custom expiration time (defaults to now + default TTL)
            metadata: Additional session metadata
            
        Returns:
            Created session
        """
        if expires_at is None:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.default_session_ttl)
        
        # Create session
        session = Session(
            authorization_id=authorization_id,
            psu_id_hash=self._hash_psu_id(psu_id),
            accounts=accounts,
            aspsp=aspsp,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        
        # Store session
        await self._store_session(session)
        
        logger.info(
            f"Session created: {session.session_id} for bank {aspsp.name} "
            f"({len(accounts)} accounts, expires at {expires_at})"
        )
        
        return session
    
    async def _store_session(self, session: Session):
        """Store session in memory and Redis."""
        # Store in memory
        with self._sessions_lock:
            self._sessions[session.session_id] = session
        
        # Store in Redis if available
        if self._redis:
            try:
                redis_key = self._get_redis_key(session.session_id)
                session_data = json.dumps(session.to_dict())
                ttl = session.time_until_expiry
                
                if ttl > 0:
                    await self._redis.setex(redis_key, ttl, session_data)
                    logger.debug(f"Session {session.session_id} stored in Redis")
            except Exception as e:
                logger.warning(f"Failed to store session in Redis: {e}")
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session if found and not expired, None otherwise
        """
        session = None
        
        # Try in-memory first
        with self._sessions_lock:
            session = self._sessions.get(session_id)
        
        # Try Redis if not found in memory
        if not session and self._redis:
            try:
                redis_key = self._get_redis_key(session_id)
                session_data = await self._redis.get(redis_key)
                
                if session_data:
                    session_dict = json.loads(session_data)
                    session = Session.from_dict(session_dict)
                    
                    # Store back in memory
                    with self._sessions_lock:
                        self._sessions[session_id] = session
                    
                    logger.debug(f"Session {session_id} loaded from Redis")
            except Exception as e:
                logger.warning(f"Failed to load session from Redis: {e}")
        
        # Check if session is expired
        if session and session.is_expired:
            logger.debug(f"Session {session_id} is expired, removing")
            await self.delete_session(session_id)
            return None
        
        # Update last accessed time
        if session:
            session.refresh_last_accessed()
            # Don't await to avoid slowing down the response
            asyncio.create_task(self._store_session(session))
        
        return session
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was deleted, False if not found
        """
        found = False
        
        # Remove from memory
        with self._sessions_lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                found = True
        
        # Remove from Redis
        if self._redis:
            try:
                redis_key = self._get_redis_key(session_id)
                deleted = await self._redis.delete(redis_key)
                found = found or (deleted > 0)
            except Exception as e:
                logger.warning(f"Failed to delete session from Redis: {e}")
        
        if found:
            logger.info(f"Session deleted: {session_id}")
        
        return found
    
    async def list_sessions(
        self,
        include_expired: bool = False,
        aspsp_name: Optional[str] = None,
    ) -> List[Session]:
        """List active sessions.
        
        Args:
            include_expired: Include expired sessions
            aspsp_name: Filter by bank name
            
        Returns:
            List of sessions
        """
        sessions = []
        
        # Get all sessions from memory
        with self._sessions_lock:
            for session in self._sessions.values():
                # Filter expired sessions
                if not include_expired and session.is_expired:
                    continue
                
                # Filter by bank name
                if aspsp_name and session.aspsp.name.lower() != aspsp_name.lower():
                    continue
                
                sessions.append(session)
        
        return sessions
    
    async def get_sessions_by_bank(self, aspsp_name: str) -> List[Session]:
        """Get all active sessions for a specific bank.
        
        Args:
            aspsp_name: Bank name
            
        Returns:
            List of active sessions for the bank
        """
        return await self.list_sessions(aspsp_name=aspsp_name)
    
    async def extend_session(
        self,
        session_id: str,
        additional_seconds: int,
    ) -> Optional[Session]:
        """Extend session expiration time.
        
        Args:
            session_id: Session identifier
            additional_seconds: Additional seconds to add to expiration
            
        Returns:
            Updated session if found, None otherwise
        """
        session = await self.get_session(session_id)
        if not session:
            return None
        
        # Extend expiration
        session.expires_at += timedelta(seconds=additional_seconds)
        
        # Store updated session
        await self._store_session(session)
        
        logger.info(f"Session {session_id} extended by {additional_seconds} seconds")
        return session
    
    async def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics.
        
        Returns:
            Dictionary with session statistics
        """
        with self._sessions_lock:
            total_sessions = len(self._sessions)
            
            active_sessions = 0
            expired_sessions = 0
            banks = set()
            
            for session in self._sessions.values():
                if session.is_expired:
                    expired_sessions += 1
                else:
                    active_sessions += 1
                    banks.add(session.aspsp.name)
        
        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "expired_sessions": expired_sessions,
            "unique_banks": len(banks),
            "redis_enabled": self._redis is not None,
        }
    
    async def _cleanup_expired_sessions(self):
        """Background task to clean up expired sessions."""
        logger.info("Session cleanup task started")
        
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                expired_sessions = []
                
                # Find expired sessions
                with self._sessions_lock:
                    for session_id, session in list(self._sessions.items()):
                        if session.is_expired:
                            expired_sessions.append(session_id)
                
                # Remove expired sessions
                for session_id in expired_sessions:
                    await self.delete_session(session_id)
                
                if expired_sessions:
                    logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
                
            except asyncio.CancelledError:
                logger.info("Session cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in session cleanup task: {e}")
                # Continue running despite errors