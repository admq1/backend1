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
    result = db.table("profiles").select("*").eq("id", user["user_id"]).execute()

    if not result.data:
        # Return a default profile if none exists (FK constraint prevents creation)
        return {
            "id": user["user_id"],
            "full_name": "RUDRX1 User",
            "plan": "free",
            "balance": 0.00,
            "tokens_used_this_month": 0,
            "token_limit": 1000000,
            "created_at": None,
            "updated_at": None,
        }

    return result.data[0]


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
