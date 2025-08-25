import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, date
from utils.jwt_handler import JWTHandler
from config.settings import settings
from models import ApplicationInfo, AuthorizationRequest, AuthorizationResponse, ASPSPListResponse, BalancesResponse, ASPSP, AccountAccess

from models import Validity

from models import CallbackParameters, CallbackResponse


class EnableBankingClient:
    def __init__(self):
        self.base_url = settings.enable_banking_base_api_url
        self.jwt_handler = JWTHandler()
        self.application_id = settings.enable_banking_application_id
        self.http_client = httpx.AsyncClient(
            timeout=30,
            headers={
                "User-Agent": "EnableBankingClient/1.0"
            }
        )
    async def initialize(self):
        self.application_info = await self.get_application_id()

    def _get_headers(self) -> Dict[str, str]:
        if not self.application_id:
            raise ValueError("ApplicationId is required")
        jwt_token = self.jwt_handler.generate_enable_baking_token()
        return {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
        }
    async def get_application_id(self) -> str:
        temp_jwt = self.jwt_handler.generate_enable_baking_token()
        headers = {
            "Authorization": f"Bearer {temp_jwt}",
            "Content-Type": "application/json",
        }
        response = await self.http_client.get(
            f"{self.base_url}/application",
            headers=headers,
        )
        response.raise_for_status()
        app_info = ApplicationInfo(**response.json())
        return app_info.kid

    async def get_aspsps(self, country: str):
        response = await self.http_client.get(
            f"{self.base_url}/aspsps",
            params={"country": country},
            headers=self._get_headers(),
        )
        response.raise_for_status()
        data = response.json()
        return ASPSPListResponse(
            aspsps=data.get("aspsps", [])
        )
    async def initiate_authorization(
            self,
            aspsp_name: str,
            aspsp_country: str,
            redirect_url: str,
            psu_type: str,
            valid_until: datetime
    ) -> AuthorizationResponse:

        auth_request = AuthorizationRequest(
            access=Validity(
                valid_until=valid_until,
            ),
            aspsp = ASPSP(
                name=aspsp_name,
                country=aspsp_country.upper(),
            ),
            state=self.application_id,
            redirect_url=redirect_url,
            psu_type=psu_type
        )
        # Convert datetime to ISO format for JSON serialization
        auth_data = auth_request.dict(exclude_none=True)
        auth_data['access']['valid_until'] = auth_data['access']['valid_until'].isoformat()

        response = await self.http_client.post(
            f"{self.base_url}/auth",
            json=auth_data,
            headers=self._get_headers(),
        )

        response.raise_for_status()
        return AuthorizationResponse(**response.json())
    async def create_session(self, code: str):
        request = CallbackParameters(code=code)
        response = await self.http_client.post(
            f"{self.base_url}/sessions",
            json=request.dict(),
            headers=self._get_headers()
        )
        response.raise_for_status()
        return CallbackResponse(**response.json())


