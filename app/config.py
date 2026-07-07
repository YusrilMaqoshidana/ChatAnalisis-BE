from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings."""

    # --- App Info ---
    APP_NAME: str = "ChatAnalisis API"
    APP_DESCRIPTION: str = "API untuk Analisis Chat WhatsApp"
    APP_VERSION: str = "1.0.0"

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --- Infrastructure ---
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "bertopic"
    MINIO_SECURE: bool = False
    REDIS_URL: str = "redis://localhost:6379/0"
    PROGRESS_TTL_SECONDS: int = 86400

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["*"]

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }

# Singleton instance
settings = Settings()
