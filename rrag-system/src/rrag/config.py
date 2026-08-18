"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "rrag-system"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql+asyncpg://rrag:rrag_dev_password@localhost:5432/rrag"
    database_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_issuer: str = "https://auth.rrag.io"
    jwt_audience: str = "https://api.rrag.io"

    # Rate Limiting
    rate_limit_unauthenticated: int = 20  # per minute
    rate_limit_authenticated: int = 300  # per minute
    rate_limit_api_key_default: int = 600  # per minute

    # Password Policy
    password_min_length: int = 12
    password_max_failed_attempts: int = 5
    password_lockout_minutes: int = 15

    # Invitation
    invitation_expire_hours: int = 72

    model_config = {"env_prefix": "", "case_sensitive": False, "env_file": ".env"}


settings = Settings()
