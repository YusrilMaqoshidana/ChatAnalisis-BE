from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings for GPU branch."""

    # --- App Info ---
    APP_NAME: str = "ChatAnalisis API"
    APP_DESCRIPTION: str = "API untuk Analisis Chat WhatsApp (GPU / Adaptive OOM)"
    APP_VERSION: str = "1.0.0"

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --- Infrastructure ---
    PROGRESS_TTL_SECONDS: int = 86400

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["https://chatanalisis.yusrilmaqoshidana.my.id"]

    # --- Device & GPU Settings ---
    DEVICE: str = "auto"  # auto | cuda | cpu
    MIN_FREE_VRAM_MB: int = 1000
    GPU_INITIAL_BATCH_SIZE: int = 64
    MAX_SEQ_LENGTH: int = 128
    USE_CUML_UMAP: bool = False
    TORCH_NUM_THREADS: int = 0

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }

# Singleton instance
settings = Settings()
