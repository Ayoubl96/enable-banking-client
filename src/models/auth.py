import uuid
from datetime import datetime
from typing import List, Dict, Optional

from models.aspsp import ASPSP
from pydantic import BaseModel
from pydantic import validator

class AllAccountId(BaseModel):
    identification: Optional[str] = None
    scheme_name: Optional[str] = None
    issuer: Optional[str] = None

class AccountId(BaseModel):
    iban: Optional[str] = None
    other: Optional[AllAccountId] = None


class AccountsAuth(BaseModel):
    account_id: Optional[AccountId]
    all_account_ids: Optional[List[AllAccountId]] = None
    account_servicer: Optional[str] = None
    name: str
    details: Optional[str] = None
    usage: Optional[str] = None
    cash_account_type: str
    product: Optional[str] = None
    currency: str
    psu_status: Optional[str] = None
    credit_limit: Optional[str] = None
    legal_age: Optional[str] = None
    postal_address: Optional[str] = None
    uid: str
    identification_hash: str
    identification_hashes: List[str]

class ApplicationInfo(BaseModel):
    name: str
    description: str
    kid: str
    environment: str
    redirect_urls: List[str]
    active: bool
    countries: List[str]
    services: List[str]


class AccountAccess(BaseModel):
    accounts: Optional[str] = None
    balances: bool
    transactions: bool
    valid_until: datetime

class Validity(BaseModel):
    valid_until: datetime
class AuthorizationRequest(BaseModel):
    access: Validity
    aspsp: ASPSP
    state: str
    redirect_url: str
    psu_type: str

    @validator("state")
    def validate_state(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("State must be a valid UUID")
        return v


class AuthorizationResponse(BaseModel):
    url: str
    authorization_id: uuid.UUID
    psu_id_hash: str

class CallbackParameters(BaseModel):
    code: str

class CallbackResponse(BaseModel):
    session_id: str
    accounts: List[AccountsAuth]
    aspsp: ASPSP
    access: AccountAccess
    psu_type: str
