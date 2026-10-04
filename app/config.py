from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings for CPU branch."""

    # --- App Info ---
    APP_NAME: str = "ChatAnalisis API"
    APP_DESCRIPTION: str = "API untuk Analisis Chat WhatsApp (CPU Optimized)"
    APP_VERSION: str = "1.0.0"

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --- Infrastructure ---
    PROGRESS_TTL_SECONDS: int = 86400

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["https://chatanalisis.yusrilmaqoshidana.my.id"]

    # --- CPU Optimization Settings ---
    TORCH_NUM_THREADS: int = 0  # 0 means auto-detect os.cpu_count()
    EMBEDDING_BATCH_SIZE: int = 64
    MAX_SEQ_LENGTH: int = 128
    ENABLE_DYNAMIC_QUANTIZATION: bool = False
    DEVICE: str = "cpu"

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }

# Singleton instance
settings = Settings()
