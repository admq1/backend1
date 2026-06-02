from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_service_key: str
    supabase_jwt_secret: str

    # Groq
    groq_api_key: str

    # Razorpay
    razorpay_key_id: str
    razorpay_key_secret: str

    # App
    app_env: str = "production"
    cors_origins: str = "https://rudrxai.cloud"
    api_base_url: str = "https://api.rudrxai.cloud"
    master_user_id: str = ""  # Your Supabase auth user ID (optional)

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
