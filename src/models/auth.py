import uuid
from datetime import datetime
from typing import List

from models.aspsp import ASPSP
from models.common import PSUType
from pydantic import BaseModel
from pydantic import validator

from models.aspsp import ASPSPListResponse
from models.common import CashAccountType


class AccountsAuth(BaseModel):
    iban: str
    currency: str
    uid: uuid.UUID
    cash_account_type: CashAccountType

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
    account: bool
    balance: bool
    transaction: bool
    valid_util: datetime

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
    aspps: List[ASPSPListResponse]
    access: AccountAccess
    psu_type: PSUType

