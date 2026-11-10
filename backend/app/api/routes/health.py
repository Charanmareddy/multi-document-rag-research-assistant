"""Health and readiness endpoints."""

from fastapi import APIRouter

from backend.app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is running."""

    return {"status": "ok", "service": get_settings().app_name}
