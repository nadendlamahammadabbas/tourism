"""FastAPI application entrypoint for Smriti heritage archive."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.assets import router as assets_router
from app.api.ops import router as ops_router
from app.api.routes import router as routes_router
from app.api.sites import router as sites_router
from app.config import settings
from app.core.errors import register_error_handlers
from app.db.session import init_tables
from app.logging import logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("smriti_api_starting", env=settings.APP_ENV, llm_mode=settings.LLM_MODE)

    # Automatically create tables in dev/test for zero-friction setup
    if settings.APP_ENV in ("dev", "test"):
        try:
            await init_tables()
            logger.info("database_tables_initialized")
        except Exception as e:
            logger.warning("database_table_init_failed", error=str(e))

    yield

    logger.info("smriti_api_shutdown")


app = FastAPI(
    title="Smriti (स्मृति) API",
    description="Living Heritage Archive API — OCR, Translation, Spatial Atlas, and 3D Depth Relief",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Register RFC 7807 problem handlers
register_error_handlers(app)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Operational endpoints
app.include_router(ops_router)

# Versioned API routes
app.include_router(assets_router, prefix="/api/v1")
app.include_router(sites_router, prefix="/api/v1")
app.include_router(routes_router, prefix="/api/v1")

# Mount local storage for derivative thumbnails and files
storage_path = settings.storage_path
app.mount("/storage", StaticFiles(directory=str(storage_path)), name="storage")


@app.get("/")
async def root():
    return {
        "app": "Smriti Living Heritage Archive",
        "docs": "/docs",
        "api_v1": "/api/v1",
        "status": "online",
    }
