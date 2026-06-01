"""
Billing — Razorpay integration, subscriptions, wallet
"""
import razorpay
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from config import get_settings
from deps import get_current_user, get_supabase

router = APIRouter()
settings = get_settings()

razorpay_client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


class AddBalanceRequest(BaseModel):
    amount: int  # in INR (minimum 100)


class VerifyPaymentRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str
    amount: int


class SubscribeRequest(BaseModel):
    plan: str  # 'pro' or 'enterprise'


@router.get("/billing")
async def get_billing(user: dict = Depends(get_current_user)):
    """Get billing overview."""
    db = get_supabase()
    user_id = user["user_id"]

    profile = db.table("profiles").select("balance, plan, tokens_used_this_month, token_limit").eq("id", user_id).single().execute()
    transactions = db.table("transactions").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(20).execute()
    subscription = db.table("subscriptions").select("*").eq("user_id", user_id).eq("status", "active").order("created_at", desc=True).limit(1).execute()

    return {
        "profile": profile.data,
        "transactions": transactions.data or [],
        "subscription": subscription.data[0] if subscription.data else None,
    }


@router.post("/billing/create-order")
async def create_order(request: AddBalanceRequest, user: dict = Depends(get_current_user)):
    """Create a Razorpay order for adding balance."""
    if request.amount < 100:
        raise HTTPException(status_code=400, detail="Minimum amount is ₹100")

    order = razorpay_client.order.create({
        "amount": request.amount * 100,  # paise
        "currency": "INR",
        "receipt": f"rudrx1_{user['user_id'][:8]}_{request.amount}",
        "notes": {"user_id": user["user_id"], "type": "wallet_recharge"},
    })

    return {
        "order_id": order["id"],
        "amount": request.amount,
        "currency": "INR",
        "key_id": settings.razorpay_key_id,
    }


@router.post("/billing/verify-payment")
async def verify_payment(request: VerifyPaymentRequest, user: dict = Depends(get_current_user)):
    """Verify Razorpay payment and credit balance."""
    db = get_supabase()
    user_id = user["user_id"]

    # Verify signature
    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": request.razorpay_order_id,
            "razorpay_payment_id": request.razorpay_payment_id,
            "razorpay_signature": request.razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Payment verification failed")

    # Credit balance
    profile = db.table("profiles").select("balance").eq("id", user_id).single().execute()
    new_balance = float(profile.data["balance"]) + request.amount

    db.table("profiles").update({"balance": new_balance}).eq("id", user_id).execute()

    # Record transaction
    db.table("transactions").insert({
        "user_id": user_id,
        "type": "credit",
        "amount": request.amount,
        "currency": "INR",
        "description": f"Added ₹{request.amount} to wallet",
        "razorpay_payment_id": request.razorpay_payment_id,
        "razorpay_order_id": request.razorpay_order_id,
        "status": "completed",
    }).execute()

    # Log activity
    db.table("activity").insert({
        "user_id": user_id,
        "type": "payment_received",
        "description": f"Added ₹{request.amount} to balance",
        "metadata": {"amount": request.amount, "payment_id": request.razorpay_payment_id},
    }).execute()

    return {"success": True, "new_balance": new_balance}


@router.get("/subscription")
async def get_subscription(user: dict = Depends(get_current_user)):
    """Get current subscription status."""
    db = get_supabase()
    result = db.table("subscriptions").select("*").eq("user_id", user["user_id"]).eq("status", "active").order("created_at", desc=True).limit(1).execute()
    return {"subscription": result.data[0] if result.data else None}
