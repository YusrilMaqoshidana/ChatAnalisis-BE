"""
User Service (Business Logic Layer)
====================================
Layer ini berisi business logic untuk user.

Best Practice:
- Service memanggil Repository, bukan langsung ke data source
- Error handling dan validasi bisnis dilakukan di sini
- Raise HTTPException di sini agar API layer tetap bersih
"""

from fastapi import HTTPException, status

from app.models.user import UserListResponse, UserResponse
from app.repositories.user_repository import user_repository


class UserService:
    """Service untuk operasi bisnis terkait User."""

    def __init__(self) -> None:
        self._repo = user_repository

    def get_users(self, search: str | None = None) -> UserListResponse:
        """
        Ambil daftar user, opsional dengan filter pencarian.

        Args:
            search: Query pencarian (nama/email). None = ambil semua.

        Returns:
            UserListResponse dengan total count dan list user.
        """
        if search:
            users = self._repo.search(search)
        else:
            users = self._repo.get_all()

        return UserListResponse(total=len(users), users=users)

    def get_user_by_id(self, user_id: int) -> UserResponse:
        """
        Ambil user berdasarkan ID.

        Args:
            user_id: ID user yang dicari.

        Returns:
            UserResponse jika ditemukan.

        Raises:
            HTTPException 404: Jika user tidak ditemukan.
        """
        user = self._repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User dengan ID {user_id} tidak ditemukan",
            )
        return user


# Singleton instance
user_service = UserService()
