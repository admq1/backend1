"""
GET /v1/usage — Usage statistics and history
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
from datetime import datetime, timedelta

from deps import get_current_user, get_supabase

router = APIRouter()


@router.get("/usage")
async def get_usage(
    days: int = Query(30, ge=1, le=90),
    user: dict = Depends(get_current_user),
):
    """Get usage statistics for the authenticated user."""
    db = get_supabase()
    user_id = user["user_id"]
    start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

    # Aggregate stats
    usage = db.table("api_usage").select("total_tokens, cost, created_at").eq("user_id", user_id).gte("created_at", start_date).execute()

    total_requests = len(usage.data) if usage.data else 0
    total_tokens = sum(r["total_tokens"] for r in (usage.data or []))
    total_cost = sum(float(r["cost"]) for r in (usage.data or []))

    # Daily breakdown
    daily = db.table("daily_usage").select("*").eq("user_id", user_id).gte("date", start_date[:10]).order("date", desc=False).execute()

    return {
        "total_requests": total_requests,
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 4),
        "period_days": days,
        "daily": daily.data or [],
    }


@router.get("/usage/requests")
async def get_recent_requests(
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """Get recent API requests."""
    db = get_supabase()
    result = db.table("api_usage").select("*").eq("user_id", user["user_id"]).order("created_at", desc=True).limit(limit).execute()
    return {"data": result.data or []}
