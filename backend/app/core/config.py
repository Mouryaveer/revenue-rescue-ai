"""
Application configuration — loaded from environment variables / .env file.
Never hard-code secrets here.
"""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_SECRET_KEY: str = "change-me"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://revenuerescue:revenuerescue@localhost:5432/revenuerescue"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Payment Provider
    PAYMENT_PROVIDER: str = "simulator"
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    # LLM
    LLM_PROVIDER: Literal["openai", "mock"] = "mock"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # LangSmith
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "revenuerescue-ai"

    # Simulation
    SIMULATION_MODE: bool = True
    SIMULATION_SEED: int = 42

    # Demo
    DEMO_MODE: bool = False

    # Feature flags
    AI_MODE: bool = False
    BASELINE_MODE: bool = False

    # Auth
    JWT_SECRET: str = "change-me-jwt"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    @field_validator("OPENAI_API_KEY", mode="before")
    @classmethod
    def validate_api_key(cls, v: str, info) -> str:
        # Don't log the key value — reference by name only
        return v


settings = Settings()
