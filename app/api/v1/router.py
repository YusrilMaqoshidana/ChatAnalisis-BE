"""
API v1 Router Aggregator
========================
Menggabungkan semua sub-routers menjadi satu router v1.

Best Practice:
- Versioning API menggunakan prefix /api/v1
- Setiap domain (users, files) punya router sendiri
- Router agregator menggabungkan semuanya
"""

from fastapi import APIRouter

from app.api.v1.files import router as files_router

router = APIRouter(prefix="/api/v1")

# Include semua sub-routers
router.include_router(files_router)
