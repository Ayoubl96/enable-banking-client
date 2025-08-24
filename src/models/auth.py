from xmlrpc.client import boolean

from pydantic import BaseModel
from pydantic_settings import BaseSettings
from pydantic.dataclasses import Field, validator
from typing import Optional, List
from datetime import datetime
from models.common import PSUType
from models.aspsp import ASPSP
import uuid

from src.models.aspsp import ASPSPListResponse
from src.models.common import CashAccountType


class AccountsAuth(BaseModel):
    iban: str
    currency: str
    uid: uuid.UUID
    cash_account_type: CashAccountType

class ApplicationInfo(BaseModel):
    kid: str

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
    psu_type: PSUType

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

