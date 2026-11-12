import base64
import httpx
from fastapi import HTTPException
from app.core.config import settings

async def token():
    if not settings.paypal_client_id or not settings.paypal_client_secret:
        raise HTTPException(status_code=503, detail="PayPal Sandbox credentials are not configured.")
    credentials = base64.b64encode(f"{settings.paypal_client_id}:{settings.paypal_client_secret}".encode()).decode()
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(f"{settings.paypal_base_url.rstrip('/')}/v1/oauth2/token", headers={"Authorization":f"Basic {credentials}","Content-Type":"application/x-www-form-urlencoded"}, data={"grant_type":"client_credentials"})
        response.raise_for_status()
        return response.json()["access_token"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Unable to authenticate with PayPal Sandbox.") from exc

async def status():
    return {"configured":bool(settings.paypal_client_id and settings.paypal_client_secret),"mode":settings.paypal_mode,"base_url":settings.paypal_base_url,"capability":"Merchant-scoped API only; personal account-wide discovery is not provided by connecting developer credentials."}

async def list_subscriptions():
    access_token = await token()
    # PayPal's subscriptions search is scoped to the merchant account represented by these credentials.
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(f"{settings.paypal_base_url.rstrip('/')}/v1/billing/subscriptions", headers={"Authorization":f"Bearer {access_token}"}, params={"page_size":20,"page":1,"total_required":"true"})
        response.raise_for_status()
        data=response.json()
        return {"source":"paypal_sandbox","subscriptions":data.get("subscriptions",[]),"total_items":data.get("total_items",0)}
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="PayPal Sandbox subscription lookup failed.") from exc
