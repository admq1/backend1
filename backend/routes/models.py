"""
GET /v1/models — List available RUDRX1 models
"""
from fastapi import APIRouter

router = APIRouter()

# Internal model mapping — NEVER expose provider names
MODEL_MAP = {
    "rudrx1-core": {
        "provider_model": "llama-3.3-70b-versatile",
        "context_window": 131072,
        "capabilities": ["chat", "function_calling", "json_mode"],
        "description": "General purpose model with advanced reasoning",
    },
    "rudrx1-code": {
        "provider_model": "llama-3.3-70b-versatile",
        "context_window": 131072,
        "capabilities": ["chat", "code_generation", "function_calling"],
        "description": "Optimized for code generation and debugging",
    },
    "rudrx1-voice": {
        "provider_model": "whisper-large-v3-turbo",
        "context_window": None,
        "capabilities": ["transcription", "translation"],
        "description": "Speech-to-text and voice processing",
    },
    "rudrx1-vision": {
        "provider_model": "llama-3.2-90b-vision-preview",
        "context_window": 32768,
        "capabilities": ["chat", "vision", "image_understanding"],
        "description": "Image understanding and visual analysis",
    },
    "rudrx1-fast": {
        "provider_model": "llama-3.1-8b-instant",
        "context_window": 131072,
        "capabilities": ["chat"],
        "description": "Fastest model for simple tasks",
    },
}


def get_provider_model(rudrx_model: str) -> str:
    """Map RUDRX1 model name to provider model. Never expose this to users."""
    if rudrx_model not in MODEL_MAP:
        return MODEL_MAP["rudrx1-core"]["provider_model"]
    return MODEL_MAP[rudrx_model]["provider_model"]


@router.get("/models")
async def list_models():
    """List all available RUDRX1 models."""
    models = []
    for model_id, info in MODEL_MAP.items():
        models.append({
            "id": model_id,
            "object": "model",
            "created": 1714000000,
            "owned_by": "rudrxai",
            "context_window": info["context_window"],
            "capabilities": info["capabilities"],
            "description": info["description"],
        })
    return {"object": "list", "data": models}


@router.get("/models/{model_id}")
async def get_model(model_id: str):
    """Get details for a specific model."""
    if model_id not in MODEL_MAP:
        return {"error": {"message": f"Model '{model_id}' not found", "type": "not_found", "code": "model_not_found"}}

    info = MODEL_MAP[model_id]
    return {
        "id": model_id,
        "object": "model",
        "created": 1714000000,
        "owned_by": "rudrxai",
        "context_window": info["context_window"],
        "capabilities": info["capabilities"],
        "description": info["description"],
    }
