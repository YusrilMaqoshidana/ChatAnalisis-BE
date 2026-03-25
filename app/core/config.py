"""
Core Configuration Module
=========================
Menggunakan Pydantic BaseSettings untuk konfigurasi aplikasi.
Settings bisa di-override via environment variables.
"""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings yang bisa dikonfigurasi via env vars."""

    # --- App Info ---
    APP_NAME: str = "ChatAnalisis API"
    APP_DESCRIPTION: str = "API untuk Analisis Chat WhatsApp"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --- File Upload ---
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 10  # Maksimal 10 MB
    ALLOWED_EXTENSIONS: list[str] = [
        ".txt", ".zip"
    ]

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

    @property
    def upload_path(self) -> Path:
        """Return Path object untuk upload directory."""
        return Path(self.UPLOAD_DIR)

    model_config = {"env_prefix": "APP_", "case_sensitive": True}


# Singleton instance — dipakai di seluruh aplikasi
settings = Settings()
