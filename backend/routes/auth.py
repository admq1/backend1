"""
Auth routes — profile management
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from deps import get_current_user, get_supabase

router = APIRouter()


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None


@router.get("/profile")
async def get_profile(user: dict = Depends(get_current_user)):
    """Get authenticated user's profile."""
    db = get_supabase()
    result = db.table("profiles").select("*").eq("id", user["user_id"]).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    return result.data


@router.patch("/profile")
async def update_profile(request: UpdateProfileRequest, user: dict = Depends(get_current_user)):
    """Update user profile."""
    db = get_supabase()
    updates = {}
    if request.full_name is not None:
        updates["full_name"] = request.full_name

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = db.table("profiles").update(updates).eq("id", user["user_id"]).execute()
    return {"success": True, "profile": result.data[0] if result.data else None}
