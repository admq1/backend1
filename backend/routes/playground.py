"""
API Playground — test completions from the browser
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
import time
import httpx

from config import get_settings
from deps import get_current_user, get_supabase, check_rate_limit
from routes.models import get_provider_model

router = APIRouter()
settings = get_settings()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class PlaygroundRequest(BaseModel):
    model: str = "rudrx1-core"
    prompt: str
    system_prompt: Optional[str] = "You are a helpful assistant."
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1024


@router.post("/playground")
async def playground(request: PlaygroundRequest, user: dict = Depends(check_rate_limit)):
    """Run a playground request — simplified interface for testing."""
    provider_model = get_provider_model(request.model)
    start_time = time.time()

    messages = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": provider_model,
        "messages": messages,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(GROQ_API_URL, json=payload, headers=headers)

    latency_ms = int((time.time() - start_time) * 1000)

    if response.status_code != 200:
        return {"error": response.json(), "latency_ms": latency_ms}

    result = response.json()
    usage = result.get("usage", {})

    # Log usage
    db = get_supabase()
    db.table("api_usage").insert({
        "user_id": user["user_id"],
        "model": request.model,
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "cost": 0,  # Playground is free for now
        "endpoint": "/v1/playground",
        "status_code": 200,
        "latency_ms": latency_ms,
    }).execute()

    return {
        "response": result["choices"][0]["message"]["content"],
        "model": request.model,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
        "latency_ms": latency_ms,
    }
