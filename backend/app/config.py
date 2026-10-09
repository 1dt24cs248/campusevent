"""Campus Intelligence & Action Platform - Configuration"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    # Database
    DATABASE_URL: str = "sqlite:///./campus.db"

    # Auth
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 8

    # Encryption (Fernet key for incident data)
    APP_ENCRYPTION_KEY: str = ""

    # Demo mode
    DEMO_MODE: bool = True

    # Timezone
    CAMPUS_TZ: str = "Asia/Kolkata"

    # AI Provider
    LLM_PROVIDER: str = "none"  # none | gemini | anthropic | openai
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""

    # Solver
    SOLVER_TIME_LIMIT_SEC: int = 8

    # Demo clock override (empty = use real time)
    DEMO_NOW: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
