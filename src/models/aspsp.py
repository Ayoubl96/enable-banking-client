from pydantic import BaseModel
from pydantic import Field
from typing import Optional, List, Dict, Any

class ASPSP(BaseModel):
    name: str
    country: str

class ASPSPListResponse(BaseModel):
    aspsps: List[ASPSP]


