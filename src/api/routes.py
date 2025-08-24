from fastapi import APIRouter, HTTPException, Query, Depends, Request, Response
from typing import Optional, List
from datetime import datetime, date, timedelta, timezone
import uuid
import httpx

router = APIRouter()

# Dependency injection
async def get_enable_banking_client(request: Request):
    if not hasattr(request.app.state, 'enable_banking_client'):
        from services.enable_banking import EnableBankingClient
        enable_banking_client = EnableBankingClient()
        await enable_banking_client.initialize()
        request.app.state.enable_banking_client = enable_banking_client
    return request.app.state.enable_banking_client

@router.get("/banks")
async def get_banks(
    country: str = Query(..., regex="^[A-Z]{2}$", description="ISO country code"),
    client = Depends(get_enable_banking_client)
):
    """Get list of available banks for a country"""
    try:
        result = await client.get_aspsps(country)
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/init")
async def init_auth(
        bank_name: str,
        bank_country: str,
        access_type: str,
        validity_hours: int,
        redirect_url: str,
        client=Depends(get_enable_banking_client)
):
    try:
        valid_until = datetime.now(timezone.utc) + timedelta(hours=validity_hours)

        auth_response = await client.initiate_authorization(
            aspsp_name=bank_name,
            aspsp_country=bank_country,
            psu_type=access_type,
            redirect_url=redirect_url,
            valid_until=valid_until.isoformat(),
        )

        return auth_response
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))

@router.post("/callback")
async def authorization_callback(
        code: str,
        client=Depends(get_enable_banking_client)
):
    try:
        result = await client.create_session(code)
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))