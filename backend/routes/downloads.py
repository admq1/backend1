"""
Downloads tracking
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Optional

from deps import get_current_user, get_supabase

router = APIRouter()


class LogDownloadRequest(BaseModel):
    platform: str
    variant: str
    version: str = "2.0.0-beta"


@router.get("/downloads")
async def get_downloads(user: dict = Depends(get_current_user)):
    """Get user's download history."""
    db = get_supabase()
    result = db.table("downloads").select("*").eq("user_id", user["user_id"]).order("created_at", desc=True).limit(20).execute()
    return {"data": result.data or []}


@router.post("/downloads")
async def log_download(request: LogDownloadRequest, user: dict = Depends(get_current_user)):
    """Log a download event."""
    db = get_supabase()
    db.table("downloads").insert({
        "user_id": user["user_id"],
        "platform": request.platform,
        "variant": request.variant,
        "version": request.version,
    }).execute()

    db.table("activity").insert({
        "user_id": user["user_id"],
        "type": "download",
        "description": f"Downloaded RUDRX1 {request.variant} for {request.platform}",
        "metadata": {"platform": request.platform, "variant": request.variant, "version": request.version},
    }).execute()

    return {"success": True}


@router.get("/downloads/stats")
async def download_stats():
    """Public download statistics."""
    db = get_supabase()
    result = db.table("downloads").select("platform", count="exact").execute()
    return {"total_downloads": result.count or 0}
