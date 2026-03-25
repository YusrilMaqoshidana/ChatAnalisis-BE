"""
Dependency Injection
====================
Menyediakan dependencies untuk API routes.
"""

from app.services.file_service import FileService, file_service


def get_file_service() -> FileService:
    """Dependency untuk mendapatkan FileService instance."""
    return file_service
