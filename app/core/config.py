"""
Core Configuration Module
=========================
Settings dikonfigurasi via environment variables (prefix APP_).
"""

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

    # --- File Upload (in-memory) ---
    MAX_FILE_SIZE_MB: int = 10  # Batas raw file yang diterima (10 MB)

    # --- Rate Limiting ---
    RATE_LIMIT_UPLOAD: str = "5/minute"  # Max upload per IP per menit

    # --- Zip Bomb Protection ---
    # Estimasi: grup aktif ~300 pesan/hari × 200 karakter × 1095 hari ≈ 65 MB, buffer 3× = 200 MB
    ZIP_MAX_EXTRACTED_MB: int = 200

    # --- Processing Timeout ---
    UPLOAD_TIMEOUT_SECONDS: int = 30

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["*"]

    @property
    def max_file_size_bytes(self) -> int:
        """Konversi MB ke bytes."""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    model_config = {"env_prefix": "APP_", "case_sensitive": True}


# Singleton instance
settings = Settings()
