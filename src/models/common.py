from pydantic_settings import BaseSettings
from pydantic import Field, BaseModel
from typing import Optional,Dict, Any
from datetime import datetime
from enum import Enum


class PSUType(str, Enum):
    """Payment Service User type"""
    PERSONAL = "personal"
    BUSINESS = "business"

class AccountUsage(str, Enum):
    """Account usage type"""
    PRIV = "PRIV"  # Private/Personal
    ORGA = "ORGA"  # Organization/Business

class CashAccountType(str, Enum):
    """Cash account type codes"""
    CACC = "CACC"  # Current Account
    CASH = "CASH"  # Cash Account
    CARD = "CARD"  # Card Account
    SVGS = "SVGS"  # Savings Account
    LOAN = "LOAN"  # Loan Account
    MGLD = "MGLD"  # Marginal Lending
    MOMA = "MOMA"  # Money Market
    NREX = "NREX"  # Non Resident External
    ODFT = "ODFT"  # Overdraft
    ONDP = "ONDP"  # Overnight Deposit
    OTHR = "OTHR"  # Other

class BalanceType(str, Enum):
    """Balance type codes"""
    CLBD = "CLBD"  # Closing Booked
    XPCD = "XPCD"  # Expected
    OPBD = "OPBD"  # Opening Booked
    ITBD = "ITBD"  # Interim Booked
    CLAV = "CLAV"  # Closing Available
    OPAV = "OPAV"  # Opening Available
    ITAV = "ITAV"  # Interim Available
    PRCD = "PRCD"  # Previously Closed Booked

class TransactionStatus(str, Enum):
    """Transaction status"""
    BOOK = "BOOK"  # Booked
    PDNG = "PDNG"  # Pending
    INFO = "INFO"  # Information

class CreditDebitIndicator(str, Enum):
    """Credit or Debit indicator"""
    CRDT = "CRDT"  # Credit
    DBIT = "DBIT"  # Debit


class Amount(BaseModel):
    amount: str = Field(...,  description="Amount as string to preserve precision")
    currency: str = Field(..., description="Currency code")

class ErrorInfo(BaseModel):
    code: str
    message: str
    details: Optional[str] = None


