import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field, validator


class Account(BaseModel):
    """Bank account model."""
    
    uid: str = Field(..., description="Account unique identifier")
    iban: Optional[str] = Field(None, description="Account IBAN")
    name: str = Field(..., description="Account name/description")
    currency: str = Field(..., description="Account currency code")
    account_type: Optional[str] = Field(None, description="Type of account")
    status: Optional[str] = Field(None, description="Account status")


class ASPSP(BaseModel):
    """Account Servicing Payment Service Provider (Bank) information."""
    
    name: str = Field(..., description="Bank name")
    country: str = Field(..., description="Bank country code (ISO 2-letter)")
    bic: Optional[str] = Field(None, description="Bank BIC code")
    logo_url: Optional[str] = Field(None, description="Bank logo URL")


class Session(BaseModel):
    """Bank authorization session model."""
    
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique session ID")
    authorization_id: str = Field(..., description="Authorization ID from Enable Banking")
    psu_id_hash: str = Field(..., description="Hashed PSU (Payment Service User) identifier")
    accounts: List[Account] = Field(default_factory=list, description="List of authorized accounts")
    aspsp: ASPSP = Field(..., description="Bank information")
    expires_at: datetime = Field(..., description="Session expiration timestamp")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Session creation timestamp")
    last_accessed: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last access timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional session metadata")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @validator("expires_at", "created_at", "last_accessed", pre=True)
    def parse_datetime(cls, v):
        """Parse datetime from string if needed."""
        if isinstance(v, str):
            # Try to parse ISO format datetime
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                # Fallback to parsing without timezone info, assume UTC
                return datetime.fromisoformat(v).replace(tzinfo=timezone.utc)
        return v
    
    @property
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.now(timezone.utc) >= self.expires_at
    
    @property
    def time_until_expiry(self) -> int:
        """Get seconds until expiry."""
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds()))
    
    def refresh_last_accessed(self) -> None:
        """Update last accessed timestamp."""
        self.last_accessed = datetime.now(timezone.utc)
    
    def add_account(self, account: Account) -> None:
        """Add account to session."""
        # Avoid duplicates
        existing_uids = {acc.uid for acc in self.accounts}
        if account.uid not in existing_uids:
            self.accounts.append(account)
    
    def get_account(self, account_uid: str) -> Optional[Account]:
        """Get account by UID."""
        for account in self.accounts:
            if account.uid == account_uid:
                return account
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "authorization_id": self.authorization_id,
            "psu_id_hash": self.psu_id_hash,
            "accounts": [acc.dict() for acc in self.accounts],
            "aspsp": self.aspsp.dict(),
            "expires_at": self.expires_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Create session from dictionary."""
        # Convert accounts
        accounts = [Account(**acc) for acc in data.get("accounts", [])]
        
        # Create session
        session_data = data.copy()
        session_data["accounts"] = accounts
        session_data["aspsp"] = ASPSP(**data["aspsp"])
        
        return cls(**session_data)