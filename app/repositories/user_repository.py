"""
User Repository (Data Access Layer)
====================================
Layer ini bertanggung jawab untuk akses data.
Saat ini menggunakan dummy data, tapi bisa diganti ke database
tanpa mengubah layer di atasnya (Service / API).

Best Practice:
- Repository hanya berisi operasi CRUD terhadap data source
- Tidak ada business logic di sini
- Return raw data, biarkan service yang memproses
"""

from datetime import datetime

from app.models.user import UserResponse, UserRole


class UserRepository:
    """Repository untuk mengakses data user (dummy)."""

    def __init__(self) -> None:
        """Inisialisasi dummy data."""
        self._users: list[UserResponse] = [
            UserResponse(
                id=1,
                name="Budi Santoso",
                email="budi.santoso@example.com",
                role=UserRole.ADMIN,
                is_active=True,
                avatar_url="https://i.pravatar.cc/150?img=1",
                created_at=datetime(2026, 1, 15, 10, 30, 0),
            ),
            UserResponse(
                id=2,
                name="Siti Nurhaliza",
                email="siti.nurhaliza@example.com",
                role=UserRole.USER,
                is_active=True,
                avatar_url="https://i.pravatar.cc/150?img=5",
                created_at=datetime(2026, 1, 20, 14, 0, 0),
            ),
            UserResponse(
                id=3,
                name="Ahmad Dahlan",
                email="ahmad.dahlan@example.com",
                role=UserRole.MODERATOR,
                is_active=True,
                avatar_url="https://i.pravatar.cc/150?img=3",
                created_at=datetime(2026, 2, 1, 9, 15, 0),
            ),
            UserResponse(
                id=4,
                name="Dewi Lestari",
                email="dewi.lestari@example.com",
                role=UserRole.USER,
                is_active=False,
                avatar_url="https://i.pravatar.cc/150?img=9",
                created_at=datetime(2026, 2, 5, 11, 45, 0),
            ),
            UserResponse(
                id=5,
                name="Eko Prasetyo",
                email="eko.prasetyo@example.com",
                role=UserRole.USER,
                is_active=True,
                avatar_url="https://i.pravatar.cc/150?img=11",
                created_at=datetime(2026, 2, 10, 8, 0, 0),
            ),
            UserResponse(
                id=6,
                name="Fitriani Wulandari",
                email="fitriani.w@example.com",
                role=UserRole.MODERATOR,
                is_active=True,
                avatar_url="https://i.pravatar.cc/150?img=20",
                created_at=datetime(2026, 2, 14, 16, 30, 0),
            ),
            UserResponse(
                id=7,
                name="Gunawan Hidayat",
                email="gunawan.h@example.com",
                role=UserRole.USER,
                is_active=True,
                avatar_url="https://i.pravatar.cc/150?img=12",
                created_at=datetime(2026, 2, 20, 13, 0, 0),
            ),
            UserResponse(
                id=8,
                name="Hana Permata",
                email="hana.permata@example.com",
                role=UserRole.USER,
                is_active=False,
                avatar_url="https://i.pravatar.cc/150?img=25",
                created_at=datetime(2026, 3, 1, 10, 0, 0),
            ),
            UserResponse(
                id=9,
                name="Irfan Maulana",
                email="irfan.maulana@example.com",
                role=UserRole.ADMIN,
                is_active=True,
                avatar_url="https://i.pravatar.cc/150?img=15",
                created_at=datetime(2026, 3, 5, 9, 30, 0),
            ),
            UserResponse(
                id=10,
                name="Joko Widodo",
                email="joko.w@example.com",
                role=UserRole.USER,
                is_active=True,
                avatar_url="https://i.pravatar.cc/150?img=17",
                created_at=datetime(2026, 3, 10, 15, 0, 0),
            ),
        ]

    def get_all(self) -> list[UserResponse]:
        """Ambil semua user."""
        return self._users

    def get_by_id(self, user_id: int) -> UserResponse | None:
        """Ambil user berdasarkan ID. Return None jika tidak ditemukan."""
        for user in self._users:
            if user.id == user_id:
                return user
        return None

    def search(self, query: str) -> list[UserResponse]:
        """
        Cari user berdasarkan nama atau email.
        Case-insensitive search.
        """
        query_lower = query.lower()
        return [
            user for user in self._users
            if query_lower in user.name.lower()
            or query_lower in user.email.lower()
        ]


# Singleton instance
user_repository = UserRepository()
