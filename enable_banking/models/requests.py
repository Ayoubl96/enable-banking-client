"""Request models for Enable Banking API."""

from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class AuthRequest(BaseModel):
    """Request model for initiating bank authorization."""
    
    aspsp: str = Field(..., description="Bank identifier (ASPSP name)")
    country: str = Field(..., description="Bank country code (ISO 2-letter)")
    redirect_uri: str = Field(..., description="Redirect URI after authorization")
    state: Optional[str] = Field(None, description="State parameter for OAuth flow")
    psu_id: Optional[str] = Field(None, description="PSU identifier")
    psu_ip_address: Optional[str] = Field(None, description="PSU IP address")
    
    @validator("country")
    def validate_country(cls, v):
        """Validate country code."""
        if len(v) != 2:
            raise ValueError("Country code must be 2 characters")
        return v.upper()


class SessionRequest(BaseModel):
    """Request model for creating session from authorization code."""
    
    code: str = Field(..., description="Authorization code from callback")
    state: Optional[str] = Field(None, description="State parameter from OAuth flow")


class TransactionFilter(BaseModel):
    """Filter parameters for transaction queries."""
    
    date_from: Optional[date] = Field(None, description="Start date for transactions")
    date_to: Optional[date] = Field(None, description="End date for transactions") 
    limit: Optional[int] = Field(100, description="Maximum number of transactions", ge=1, le=1000)
    offset: Optional[int] = Field(0, description="Offset for pagination", ge=0)
    booking_status: Optional[str] = Field(None, description="Booking status filter")
    
    @validator("date_to")
    def validate_date_range(cls, v, values):
        """Validate that date_to is after date_from."""
        date_from = values.get("date_from")
        if date_from and v and v < date_from:
            raise ValueError("date_to must be after date_from")
        return v


class BalanceRequest(BaseModel):
    """Request model for account balances."""
    
    account_uid: str = Field(..., description="Account unique identifier")


class TransactionRequest(BaseModel):
    """Request model for account transactions."""
    
    account_uid: str = Field(..., description="Account unique identifier")
    filters: Optional[TransactionFilter] = Field(None, description="Transaction filters")
    
    def to_query_params(self) -> Dict[str, Any]:
        """Convert to query parameters for API request."""
        params = {}
        
        if self.filters:
            if self.filters.date_from:
                params["date_from"] = self.filters.date_from.isoformat()
            if self.filters.date_to:
                params["date_to"] = self.filters.date_to.isoformat()
            if self.filters.limit:
                params["limit"] = self.filters.limit
            if self.filters.offset:
                params["offset"] = self.filters.offset
            if self.filters.booking_status:
                params["booking_status"] = self.filters.booking_status
        
        return params