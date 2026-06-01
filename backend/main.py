"""
RUDRX1 Backend API — Production Server
https://api.rudrxai.cloud/v1
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from config import get_settings
from routes import models, chat, usage, billing, keys, auth, downloads, activity, playground

settings = get_settings()

app = FastAPI(
    title="RUDRX1 API",
    description="Production API for the RUDRX1 AI Platform",
    version="2.0.0",
    docs_url="/v1/docs",
    redoc_url="/v1/redoc",
)

# CORS
origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"service": "RUDRX1 API", "version": "2.0.0", "status": "operational"}


@app.get("/v1")
async def v1_root():
    return {
        "service": "RUDRX1 API",
        "version": "2.0.0",
        "endpoints": {
            "models": "/v1/models",
            "chat": "/v1/chat/completions",
            "usage": "/v1/usage",
            "billing": "/v1/billing",
            "keys": "/v1/keys",
            "downloads": "/v1/downloads",
        },
    }


# Register routers
app.include_router(auth.router, prefix="/v1/auth", tags=["Authentication"])
app.include_router(models.router, prefix="/v1", tags=["Models"])
app.include_router(chat.router, prefix="/v1", tags=["Chat"])
app.include_router(keys.router, prefix="/v1", tags=["API Keys"])
app.include_router(usage.router, prefix="/v1", tags=["Usage"])
app.include_router(billing.router, prefix="/v1", tags=["Billing"])
app.include_router(downloads.router, prefix="/v1", tags=["Downloads"])
app.include_router(activity.router, prefix="/v1", tags=["Activity"])
app.include_router(playground.router, prefix="/v1", tags=["Playground"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
