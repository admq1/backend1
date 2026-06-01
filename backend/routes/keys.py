"""
API Key Management — Create, Delete, Regenerate
"""
import hashlib
import secrets
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from deps import get_current_user, get_supabase

router = APIRouter()


class CreateKeyRequest(BaseModel):
    name: str = "Default"


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key. Returns (full_key, prefix, hash)."""
    random_part = secrets.token_hex(16)
    full_key = f"rx-{random_part}"
    prefix = f"rx-{random_part[:4]}****{random_part[-4:]}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, prefix, key_hash


@router.get("/keys")
async def list_keys(user: dict = Depends(get_current_user)):
    """List all active API keys for the user."""
    db = get_supabase()
    result = db.table("api_keys").select("id, name, key_prefix, last_used_at, is_active, created_at").eq("user_id", user["user_id"]).eq("is_active", True).order("created_at", desc=True).execute()
    return {"data": result.data or []}


@router.post("/keys")
async def create_key(request: CreateKeyRequest, user: dict = Depends(get_current_user)):
    """Create a new API key."""
    db = get_supabase()
    full_key, prefix, key_hash = generate_api_key()

    result = db.table("api_keys").insert({
        "user_id": user["user_id"],
        "name": request.name,
        "key_prefix": prefix,
        "key_hash": key_hash,
    }).execute()

    # Log activity
    db.table("activity").insert({
        "user_id": user["user_id"],
        "type": "api_key_created",
        "description": f'Created API key "{request.name}"',
        "metadata": {"key_id": result.data[0]["id"]},
    }).execute()

    return {
        "id": result.data[0]["id"],
        "name": request.name,
        "key": full_key,  # Only shown once
        "key_prefix": prefix,
        "created_at": result.data[0]["created_at"],
    }


@router.delete("/keys/{key_id}")
async def delete_key(key_id: str, user: dict = Depends(get_current_user)):
    """Soft-delete an API key."""
    db = get_supabase()
    result = db.table("api_keys").update({"is_active": False}).eq("id", key_id).eq("user_id", user["user_id"]).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="API key not found")

    db.table("activity").insert({
        "user_id": user["user_id"],
        "type": "api_key_deleted",
        "description": "Deleted an API key",
        "metadata": {"key_id": key_id},
    }).execute()

    return {"success": True}


@router.post("/keys/{key_id}/regenerate")
async def regenerate_key(key_id: str, user: dict = Depends(get_current_user)):
    """Regenerate an API key (new key, same record)."""
    db = get_supabase()
    full_key, prefix, key_hash = generate_api_key()

    result = db.table("api_keys").update({
        "key_prefix": prefix,
        "key_hash": key_hash,
    }).eq("id", key_id).eq("user_id", user["user_id"]).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="API key not found")

    db.table("activity").insert({
        "user_id": user["user_id"],
        "type": "api_key_regenerated",
        "description": "Regenerated an API key",
        "metadata": {"key_id": key_id},
    }).execute()

    return {
        "id": key_id,
        "key": full_key,
        "key_prefix": prefix,
    }
