"""
User API Endpoints
==================
Semua endpoint terkait User ada di sini.

Best Practice:
- Route handler hanya berisi: parse input → panggil service → return response
- Tidak ada business logic di route handler
- Gunakan type hints dan response_model untuk dokumentasi otomatis
- Tambahkan docstring untuk Swagger UI
"""

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_user_service
from app.models.user import UserListResponse, UserResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "",
    response_model=UserListResponse,
    summary="Ambil daftar user",
    description="Mengambil daftar semua user. Bisa difilter menggunakan query parameter `search`.",
)
def get_users(
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
        description="Cari user berdasarkan nama atau email",
        examples=["budi"],
    ),
    service: UserService = Depends(get_user_service),
) -> UserListResponse:
    """
    **Daftar User**

    - Tanpa parameter: mengembalikan semua user
    - Dengan `search`: filter berdasarkan nama atau email (case-insensitive)

    **Contoh request:**
    - `GET /api/v1/users` → semua user
    - `GET /api/v1/users?search=budi` → user yang mengandung "budi"
    """
    return service.get_users(search=search)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Ambil user berdasarkan ID",
    description="Mengambil detail user berdasarkan ID. Return 404 jika tidak ditemukan.",
    responses={
        404: {
            "description": "User tidak ditemukan",
            "content": {
                "application/json": {
                    "example": {"detail": "User dengan ID 999 tidak ditemukan"}
                }
            },
        }
    },
)
def get_user_by_id(
    user_id: int,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """
    **Detail User**

    Mengambil detail lengkap user berdasarkan ID.

    **Responses:**
    - `200`: User ditemukan
    - `404`: User tidak ditemukan
    """
    return service.get_user_by_id(user_id)
