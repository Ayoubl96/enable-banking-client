from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from models.common import Amount, BalanceType, TransactionStatus, CreditDebitIndicator
from tomlkit.api import value

class Balance(BaseModel):
    name: str
    balance_amount: Amount
    balance_type: BalanceType
    last_change_date_time: Optional[datetime] = None
    reference_date: Optional[datetime] = None

class BalancesResponse(BaseModel):
    balances: List[Balance]
    account_uid: Optional[str] = None


class AccountId(BaseModel):
    account_id: str = Field(..., description="The unique identifier of the account")

class AmountType(BaseModel):
    amount: Amount
    currency: str

class Transaction(BaseModel):
    entry_reference: Optional[str] = None,
    merchant_category_code: Optional[str] = None
    transaction_amount: AmountType
    status: str
    booking_date: Optional[datetime] = None
    value_date: Optional[datetime] = None
    transaction_date: Optional[datetime] = None

class TransactionsResponse(BaseModel):
    transactions: List[Transaction]
