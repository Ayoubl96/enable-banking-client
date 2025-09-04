from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from models.common import Amount, BalanceType, TransactionStatus, CreditDebitIndicator

class Balance(BaseModel):
    name: str
    balance_amount: Amount
    balance_type: BalanceType
    last_change_date_time: Optional[datetime] = None
    reference_date: Optional[datetime] = None

class BalancesResponse(BaseModel):
    balances: List[Balance]
    account_uid: Optional[str] = None

