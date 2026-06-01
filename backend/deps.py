"""
Dependencies — Auth, DB, Rate Limiting
"""
from fastapi import Depends, HTTPException, Header
from jose import jwt, JWTError
from supabase import create_client, Client
from config import get_settings
import hashlib
import time

settings = get_settings()

# Supabase client (service role — full access)
supabase: Client = create_client(settings.supabase_url, settings.supabase_service_key)


def get_supabase() -> Client:
    return supabase


async def get_current_user(authorization: str = Header(...)):
    """Validate JWT from Supabase Auth or API Key."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.replace("Bearer ", "")

    # Check if it's an API key (starts with rx-)
    if token.startswith("rx-"):
        return await validate_api_key(token)

    # Otherwise treat as JWT
    return await validate_jwt(token)


async def validate_jwt(token: str) -> dict:
    """Validate Supabase JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"user_id": user_id, "auth_type": "jwt"}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def validate_api_key(key: str) -> dict:
    """Validate API key against database."""
    key_hash = hashlib.sha256(key.encode()).hexdigest()

    result = supabase.table("api_keys").select("id, user_id, is_active").eq("key_hash", key_hash).eq("is_active", True).execute()

    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid API key")

    api_key = result.data[0]

    # Update last_used_at
    supabase.table("api_keys").update({"last_used_at": "now()"}).eq("id", api_key["id"]).execute()

    return {"user_id": api_key["user_id"], "auth_type": "api_key", "key_id": api_key["id"]}


async def check_rate_limit(user: dict = Depends(get_current_user)):
    """Check if user has exceeded rate limits."""
    user_id = user["user_id"]

    # Get user profile for plan
    profile = supabase.table("profiles").select("plan, tokens_used_this_month, token_limit").eq("id", user_id).single().execute()

    if not profile.data:
        raise HTTPException(status_code=403, detail="User profile not found")

    if profile.data["tokens_used_this_month"] >= profile.data["token_limit"]:
        raise HTTPException(
            status_code=429,
            detail="Monthly token limit exceeded. Upgrade your plan or add balance.",
            headers={"x-ratelimit-limit-tokens": str(profile.data["token_limit"]), "x-ratelimit-remaining-tokens": "0"},
        )

    return {**user, "profile": profile.data}


async def check_balance(user: dict = Depends(get_current_user)):
    """Check if user has sufficient balance for pay-as-you-go."""
    user_id = user["user_id"]
    profile = supabase.table("profiles").select("balance, plan").eq("id", user_id).single().execute()

    if not profile.data:
        raise HTTPException(status_code=403, detail="User profile not found")

    return {**user, "profile": profile.data}
