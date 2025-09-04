import uuid
from datetime import datetime
from typing import List, Dict, Optional

from models import AccountAccess
from models.aspsp import ASPSP
from pydantic import BaseModel

class SessionParameters(BaseModel):
    session_id: str

class AccountsData(BaseModel):
    uid: str
    identification_hash: str
    identification_hashes: List[str]

class SessionResponse(BaseModel):
    status: str
    accounts: List[str]
    accounts_data: List[AccountsData]
    aspsp: ASPSP
    psu_type: str
    psu_id_hash: str
    access: AccountAccess
    created: datetime
    authorized: datetime
    closed: Optional[datetime]
