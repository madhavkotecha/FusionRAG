from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://rrag:rrag_dev_password@localhost:5432/rrag"
    redis_url: str = "redis://localhost:6381/0"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8080
    cors_origins: str = "http://localhost:5173,http://localhost:8000"

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
