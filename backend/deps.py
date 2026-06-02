"""
Dependencies — Auth, DB, Rate Limiting, Auto-Provisioning
"""
from fastapi import Depends, HTTPException, Header
from jose import jwt, JWTError
from supabase import create_client, Client
from config import get_settings
import hashlib
import uuid

settings = get_settings()

# Supabase client (service role — full access)
supabase: Client = create_client(settings.supabase_url, settings.supabase_service_key)

# Master/default user ID for auto-provisioned keys
# Set this to your own Supabase auth user ID once you sign up
MASTER_USER_ID = settings.master_user_id if hasattr(settings, 'master_user_id') else None


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

        # Auto-create profile if missing
        await ensure_profile_exists(user_id)

        return {"user_id": user_id, "auth_type": "jwt"}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def validate_api_key(key: str) -> dict:
    """
    Validate API key against database.
    If key doesn't exist, AUTO-PROVISION it (register on first use).
    """
    key_hash = hashlib.sha256(key.encode()).hexdigest()

    result = supabase.table("api_keys").select("id, user_id, is_active").eq("key_hash", key_hash).eq("is_active", True).execute()

    if not result.data:
        # AUTO-PROVISION: Register this key automatically
        user_id = await auto_provision_key(key, key_hash)
        # Fetch the newly created key
        result = supabase.table("api_keys").select("id, user_id, is_active").eq("key_hash", key_hash).eq("is_active", True).execute()
        if not result.data:
            raise HTTPException(status_code=401, detail="Failed to provision API key")

    api_key = result.data[0]

    # Update last_used_at
    supabase.table("api_keys").update({"last_used_at": "now()"}).eq("id", api_key["id"]).execute()

    return {"user_id": api_key["user_id"], "auth_type": "api_key", "key_id": api_key["id"]}


async def auto_provision_key(key: str, key_hash: str) -> str:
    """
    Auto-provision an API key on first use.
    Creates a user profile and registers the key.
    """
    # Determine user ID — use master user or create a system user
    user_id = MASTER_USER_ID
    if not user_id:
        user_id = str(uuid.uuid4())

    # Ensure profile exists
    await ensure_profile_exists(user_id)

    # Create the API key record
    prefix = key[:7] + "****" + key[-4:]
    supabase.table("api_keys").insert({
        "user_id": user_id,
        "name": "Auto-provisioned",
        "key_prefix": prefix,
        "key_hash": key_hash,
        "is_active": True,
    }).execute()

    # Log activity
    try:
        supabase.table("activity").insert({
            "user_id": user_id,
            "type": "api_key_created",
            "description": f"API key auto-provisioned on first use",
            "metadata": {"auto": True},
        }).execute()
    except Exception:
        pass  # Activity logging is non-critical

    return user_id


async def ensure_profile_exists(user_id: str):
    """Create a profile if it doesn't exist yet."""
    existing = supabase.table("profiles").select("id").eq("id", user_id).execute()
    if not existing.data:
        try:
            supabase.table("profiles").insert({
                "id": user_id,
                "full_name": "RUDRX1 User",
                "plan": "free",
                "balance": 0.00,
                "tokens_used_this_month": 0,
                "token_limit": 1000000,  # 1M tokens free
            }).execute()
        except Exception:
            pass  # Profile might already exist due to race condition


async def check_rate_limit(user: dict = Depends(get_current_user)):
    """Check if user has exceeded rate limits."""
    user_id = user["user_id"]

    # Get user profile for plan
    profile = supabase.table("profiles").select("plan, tokens_used_this_month, token_limit, balance").eq("id", user_id).single().execute()

    if not profile.data:
        raise HTTPException(status_code=403, detail="User profile not found")

    # Allow if under token limit OR has balance (pay-as-you-go)
    if profile.data["tokens_used_this_month"] >= profile.data["token_limit"]:
        if float(profile.data["balance"]) <= 0:
            raise HTTPException(
                status_code=429,
                detail="Monthly token limit exceeded. Upgrade your plan or add balance.",
                headers={
                    "x-ratelimit-limit-tokens": str(profile.data["token_limit"]),
                    "x-ratelimit-remaining-tokens": "0",
                },
            )

    return {**user, "profile": profile.data}


async def check_balance(user: dict = Depends(get_current_user)):
    """Check if user has sufficient balance for pay-as-you-go."""
    user_id = user["user_id"]
    profile = supabase.table("profiles").select("balance, plan").eq("id", user_id).single().execute()

    if not profile.data:
        raise HTTPException(status_code=403, detail="User profile not found")

    return {**user, "profile": profile.data}
