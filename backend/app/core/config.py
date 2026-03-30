"""
Application configuration settings
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
import os
import json

class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "AI Code Review Assistant"
    PROJECT_NAME: str = "AI Code Review Assistant"
    PROJECT_DESCRIPTION: str = "AI-powered tool to review and analyze code"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    APP_BASE_URL: str = "http://localhost:8000"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"

    # CORS - FIX: Add all necessary origins including port 3000
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173", 
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/codereview_db"

    # Security / JWT
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # AI Services
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    OPENAI_API_KEY: Optional[str] = None

    # GitHub / GitLab Integration
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    GITLAB_CLIENT_ID: Optional[str] = None
    GITLAB_CLIENT_SECRET: Optional[str] = None
    GITHUB_ACCESS_TOKEN: Optional[str] = None  # Add this line

    # Redis
    REDIS_URL: Optional[str] = "redis://localhost:6379"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"
        
        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str):
            if field_name == "ALLOWED_ORIGINS" and raw_val:
                try:
                    return json.loads(raw_val)
                except:
                    return [origin.strip() for origin in raw_val.split(",")]
            return raw_val


# Create global settings instance
settings = Settings()

# Override with environment variables
if os.getenv("DATABASE_URL"):
    settings.DATABASE_URL = os.getenv("DATABASE_URL")
if os.getenv("GEMINI_API_KEY"):
    settings.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if os.getenv("GEMINI_MODEL"):
    settings.GEMINI_MODEL = os.getenv("GEMINI_MODEL")

# Parse ALLOWED_ORIGINS from environment if provided as string
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
if allowed_origins_env:
    try:
        settings.ALLOWED_ORIGINS = json.loads(allowed_origins_env)
    except:
        settings.ALLOWED_ORIGINS = [origin.strip() for origin in allowed_origins_env.split(",")]

# Log the configuration
print(f"✅ Using database: {settings.DATABASE_URL.split('@')[0].split('://')[0]} database")
print(f"✅ CORS origins: {settings.ALLOWED_ORIGINS}")
print(f"✅ Gemini model: {settings.GEMINI_MODEL}")