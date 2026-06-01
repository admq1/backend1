"""
POST /v1/chat/completions — Chat completions via Groq
"""
import time
import uuid
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import httpx

from config import get_settings
from deps import get_current_user, get_supabase, check_rate_limit
from routes.models import get_provider_model, MODEL_MAP

router = APIRouter()
settings = get_settings()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Pricing per 1K tokens (in INR)
PRICING = {
    "rudrx1-core": {"input": 0.50, "output": 1.50},
    "rudrx1-code": {"input": 0.50, "output": 1.50},
    "rudrx1-vision": {"input": 1.00, "output": 3.00},
    "rudrx1-fast": {"input": 0.10, "output": 0.30},
}


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "rudrx1-core"
    messages: list[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 4096
    stream: Optional[bool] = False
    top_p: Optional[float] = 1.0
    tools: Optional[list] = None
    response_format: Optional[dict] = None


@router.post("/chat/completions")
async def chat_completions(request: ChatRequest, user: dict = Depends(check_rate_limit)):
    """Create a chat completion. Routes through Groq."""
    user_id = user["user_id"]
    db = get_supabase()

    # Validate model
    if request.model not in MODEL_MAP:
        raise HTTPException(status_code=400, detail=f"Model '{request.model}' not found. Use /v1/models to list available models.")

    provider_model = get_provider_model(request.model)
    start_time = time.time()

    # Build Groq request
    groq_payload = {
        "model": provider_model,
        "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "top_p": request.top_p,
        "stream": request.stream,
    }

    if request.tools:
        groq_payload["tools"] = request.tools
    if request.response_format:
        groq_payload["response_format"] = request.response_format

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    if request.stream:
        return StreamingResponse(
            stream_groq_response(groq_payload, headers, user_id, request.model, start_time, db),
            media_type="text/event-stream",
        )

    # Non-streaming request
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(GROQ_API_URL, json=groq_payload, headers=headers)

    if response.status_code != 200:
        error_body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"message": response.text}
        raise HTTPException(status_code=response.status_code, detail=error_body)

    result = response.json()
    latency_ms = int((time.time() - start_time) * 1000)

    # Extract usage
    usage = result.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)

    # Calculate cost
    pricing = PRICING.get(request.model, PRICING["rudrx1-core"])
    cost = (input_tokens / 1000 * pricing["input"]) + (output_tokens / 1000 * pricing["output"])

    # Log usage
    await log_usage(db, user_id, user.get("key_id"), request.model, input_tokens, output_tokens, total_tokens, cost, latency_ms)

    # Deduct balance
    await deduct_balance(db, user_id, cost, total_tokens)

    # Rewrite response to use RUDRX1 model names
    result["model"] = request.model
    result["id"] = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    return result


async def stream_groq_response(payload, headers, user_id, model, start_time, db):
    """Stream response from Groq and log usage after completion."""
    total_output_tokens = 0
    input_tokens = 0

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", GROQ_API_URL, json=payload, headers=headers) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        yield f"data: [DONE]\n\n"
                        break

                    try:
                        chunk = json.loads(data)
                        # Rewrite model name
                        chunk["model"] = model
                        # Track tokens from usage field if present
                        if "usage" in chunk:
                            input_tokens = chunk["usage"].get("prompt_tokens", 0)
                            total_output_tokens = chunk["usage"].get("completion_tokens", 0)

                        yield f"data: {json.dumps(chunk)}\n\n"
                    except json.JSONDecodeError:
                        yield f"data: {data}\n\n"

    # Log usage after stream completes
    latency_ms = int((time.time() - start_time) * 1000)
    total_tokens = input_tokens + total_output_tokens
    pricing = PRICING.get(model, PRICING["rudrx1-core"])
    cost = (input_tokens / 1000 * pricing["input"]) + (total_output_tokens / 1000 * pricing["output"])

    await log_usage(db, user_id, None, model, input_tokens, total_output_tokens, total_tokens, cost, latency_ms)
    await deduct_balance(db, user_id, cost, total_tokens)


async def log_usage(db, user_id, key_id, model, input_tokens, output_tokens, total_tokens, cost, latency_ms):
    """Log API usage to database."""
    db.table("api_usage").insert({
        "user_id": user_id,
        "api_key_id": key_id,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost": float(cost),
        "endpoint": "/v1/chat/completions",
        "status_code": 200,
        "latency_ms": latency_ms,
    }).execute()

    # Update daily_usage aggregate
    today = time.strftime("%Y-%m-%d")
    existing = db.table("daily_usage").select("*").eq("user_id", user_id).eq("date", today).execute()

    if existing.data:
        row = existing.data[0]
        db.table("daily_usage").update({
            "requests": row["requests"] + 1,
            "tokens": row["tokens"] + total_tokens,
            "cost": float(row["cost"]) + float(cost),
        }).eq("id", row["id"]).execute()
    else:
        db.table("daily_usage").insert({
            "user_id": user_id,
            "date": today,
            "requests": 1,
            "tokens": total_tokens,
            "cost": float(cost),
        }).execute()


async def deduct_balance(db, user_id, cost, total_tokens):
    """Deduct cost from user balance and update token count."""
    profile = db.table("profiles").select("balance, tokens_used_this_month").eq("id", user_id).single().execute()
    if profile.data:
        new_balance = max(0, float(profile.data["balance"]) - float(cost))
        new_tokens = profile.data["tokens_used_this_month"] + total_tokens
        db.table("profiles").update({
            "balance": new_balance,
            "tokens_used_this_month": new_tokens,
        }).eq("id", user_id).execute()
