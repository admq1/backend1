"""
Activity feed
"""
from fastapi import APIRouter, Depends, Query

from deps import get_current_user, get_supabase

router = APIRouter()


@router.get("/activity")
async def get_activity(
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """Get user's activity feed."""
    db = get_supabase()
    result = db.table("activity").select("*").eq("user_id", user["user_id"]).order("created_at", desc=True).limit(limit).execute()
    return {"data": result.data or []}
