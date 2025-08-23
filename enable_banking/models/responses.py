"""Response models for Enable Banking API."""

from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from pydantic import BaseModel, Field, validator


class ApplicationInfo(BaseModel):
    """Application information response."""
    
    application_id: str = Field(..., description="Application identifier")
    name: str = Field(..., description="Application name")
    status: str = Field(..., description="Application status")
    created_at: datetime = Field(..., description="Application creation timestamp")
    permissions: List[str] = Field(default_factory=list, description="Application permissions")


class AuthResponse(BaseModel):
    """Authorization initiation response."""
    
    authorization_id: str = Field(..., description="Authorization identifier")
    auth_url: str = Field(..., description="URL for user authorization")
    expires_at: datetime = Field(..., description="Authorization expiration timestamp")
    state: Optional[str] = Field(None, description="State parameter")


class Amount(BaseModel):
    """Monetary amount model."""
    
    value: Decimal = Field(..., description="Amount value")
    currency: str = Field(..., description="Currency code (ISO 4217)")
    
    @validator("currency")
    def validate_currency(cls, v):
        """Validate currency code."""
        if len(v) != 3:
            raise ValueError("Currency code must be 3 characters")
        return v.upper()


class Balance(BaseModel):
    """Account balance model."""
    
    balance_type: str = Field(..., description="Type of balance (e.g., 'expected', 'available')")
    amount: Amount = Field(..., description="Balance amount")
    reference_date: Optional[date] = Field(None, description="Balance reference date")
    last_change_date: Optional[datetime] = Field(None, description="Last balance change timestamp")


class BalanceResponse(BaseModel):
    """Account balances response."""
    
    account_uid: str = Field(..., description="Account unique identifier")
    balances: List[Balance] = Field(..., description="List of account balances")
    updated_at: datetime = Field(..., description="Last update timestamp")


class TransactionAccount(BaseModel):
    """Transaction account information."""
    
    iban: Optional[str] = Field(None, description="Account IBAN")
    name: Optional[str] = Field(None, description="Account name")
    currency: Optional[str] = Field(None, description="Account currency")


class RemittanceInfo(BaseModel):
    """Transaction remittance information."""
    
    unstructured: Optional[List[str]] = Field(None, description="Unstructured remittance info")
    structured: Optional[Dict[str, Any]] = Field(None, description="Structured remittance info")


class Transaction(BaseModel):
    """Bank transaction model."""
    
    transaction_id: str = Field(..., description="Transaction identifier")
    end_to_end_id: Optional[str] = Field(None, description="End-to-end identifier")
    booking_date: Optional[date] = Field(None, description="Booking date")
    value_date: Optional[date] = Field(None, description="Value date")
    transaction_amount: Amount = Field(..., description="Transaction amount")
    currency_exchange: Optional[Dict[str, Any]] = Field(None, description="Currency exchange info")
    creditor_name: Optional[str] = Field(None, description="Creditor name")
    creditor_account: Optional[TransactionAccount] = Field(None, description="Creditor account")
    debtor_name: Optional[str] = Field(None, description="Debtor name")
    debtor_account: Optional[TransactionAccount] = Field(None, description="Debtor account")
    remittance_information: Optional[RemittanceInfo] = Field(None, description="Remittance info")
    additional_information: Optional[str] = Field(None, description="Additional information")
    purpose_code: Optional[str] = Field(None, description="Purpose code")
    bank_transaction_code: Optional[str] = Field(None, description="Bank transaction code")
    proprietary_bank_transaction_code: Optional[str] = Field(None, description="Proprietary bank code")
    balance_after_transaction: Optional[Amount] = Field(None, description="Balance after transaction")
    booking_status: Optional[str] = Field(None, description="Booking status")


class TransactionResponse(BaseModel):
    """Account transactions response."""
    
    account_uid: str = Field(..., description="Account unique identifier")
    transactions: List[Transaction] = Field(..., description="List of transactions")
    total_count: Optional[int] = Field(None, description="Total number of transactions")
    has_more: bool = Field(False, description="Whether more transactions are available")
    next_offset: Optional[int] = Field(None, description="Offset for next page")
    updated_at: datetime = Field(..., description="Last update timestamp")


class SessionResponse(BaseModel):
    """Session creation response."""
    
    session_id: str = Field(..., description="Session identifier")
    authorization_id: str = Field(..., description="Authorization identifier")
    psu_id: str = Field(..., description="PSU identifier")
    accounts: List[Dict[str, Any]] = Field(..., description="Authorized accounts")
    aspsp: Dict[str, Any] = Field(..., description="Bank information")
    expires_at: datetime = Field(..., description="Session expiration timestamp")
    created_at: datetime = Field(..., description="Session creation timestamp")


class ErrorResponse(BaseModel):
    """API error response."""
    
    error: str = Field(..., description="Error type")
    error_description: Optional[str] = Field(None, description="Error description")
    message: Optional[str] = Field(None, description="Error message")
    code: Optional[str] = Field(None, description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: Optional[datetime] = Field(None, description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request identifier")