"""
Application configuration — loaded from environment variables / .env file.
Never hard-code secrets here.
"""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # App
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_SECRET_KEY: str = "change-me"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://revenuerescue:revenuerescue@localhost:5432/revenuerescue"
    )

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Payment & Safety
    PAYMENT_PROVIDER: Literal["simulator", "razorpay_test", "disabled"] = "simulator"
    PAYMENT_MODE: Literal["simulation", "test", "live"] = "simulation"
    ALLOW_REAL_PAYMENTS: bool = (
        False  # Strict safety invariant: Real financial transactions disabled by default
    )
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # ML Model (LightGBM)
    LIGHTGBM_MODEL_PATH: str = "models/artifacts/lightgbm_recovery_model.joblib"

    # LLM / Serverless Reasoning Provider
    LLM_PROVIDER: Literal[
        "deterministic", "mock", "cloudflare", "cloudflare_workers_ai", "openai"
    ] = "deterministic"
    REASONING_PROVIDER: str = "deterministic"
    REASONING_MODEL: str = "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b"
    CLOUDFLARE_ACCOUNT_ID: str = ""
    CLOUDFLARE_API_TOKEN: str = ""
    LLM_TIMEOUT_SECONDS: float = 30.0
    MAX_LLM_OUTPUT_TOKENS: int = 512
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # Port for Cloud Hosting (Render / Koyeb)
    PORT: int = 8000

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
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
    ]

    @property
    def razorpay_test_ready(self) -> bool:
        """True only for a complete Test Mode configuration; never accept Live keys."""
        return (
            self.PAYMENT_PROVIDER == "razorpay_test"
            and self.RAZORPAY_KEY_ID.startswith("rzp_test_")
            and bool(self.RAZORPAY_KEY_SECRET)
        )

    @field_validator("OPENAI_API_KEY", mode="before")
    @classmethod
    def validate_api_key(cls, v: str, info) -> str:
        # Don't log the key value — reference by name only
        return v


settings = Settings()
