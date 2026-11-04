"""Operational endpoints: health, readiness, and metrics."""

import os

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.db.session import check_db_health

router = APIRouter(tags=["Operations"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Lightweight liveness probe."""
    return {"status": "ok", "app": "smriti", "env": settings.APP_ENV}


@router.get("/ready")
async def readiness_check() -> JSONResponse:
    """Readiness probe checking database connectivity and storage directory."""
    db_ok = await check_db_health()
    storage_ok = settings.storage_path.exists()

    if db_ok and storage_ok:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ready",
                "database": "connected",
                "storage": "writable",
                "llm_mode": settings.LLM_MODE,
            },
        )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "not_ready",
            "database": "connected" if db_ok else "unreachable",
            "storage": "writable" if storage_ok else "inaccessible",
        },
    )


@router.get("/metrics")
async def metrics() -> dict[str, int | str]:
    """Basic operational telemetry metrics."""
    return {
        "pid": os.getpid(),
        "app_env": settings.APP_ENV,
        "llm_mode": settings.LLM_MODE,
    }

