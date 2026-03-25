"""
Dependency Injection
====================
Menyediakan dependencies yang bisa di-inject ke API routes.

Best Practice:
- Gunakan Depends() di FastAPI untuk dependency injection
- Memudahkan testing (bisa di-mock)
- Centralize semua dependencies di satu tempat
"""

from app.services.file_service import FileService, file_service
from app.services.user_service import UserService, user_service


def get_user_service() -> UserService:
    """Dependency untuk mendapatkan UserService instance."""
    return user_service


def get_file_service() -> FileService:
    """Dependency untuk mendapatkan FileService instance."""
    return file_service
