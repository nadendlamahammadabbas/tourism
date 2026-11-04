"""Database session setup and connection management."""

import sys
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import Base

if sys.platform == "win32":
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# Normalize postgresql:// to postgresql+psycopg:// if needed
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

# SQLite for testing/fallback requires special connect args
connect_args = {}
if "sqlite" in db_url:
    connect_args["check_same_thread"] = False

engine = create_async_engine(
    db_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def _activate_sqlite_fallback():
    global engine, AsyncSessionLocal
    fallback_url = "sqlite+aiosqlite:///smriti.db"
    engine = create_async_engine(fallback_url, connect_args={"check_same_thread": False})
    AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_db_health() -> bool:
    """Check database connectivity."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception:
        if settings.APP_ENV in ("dev", "test"):
            _activate_sqlite_fallback()
            return True
        return False


async def init_tables() -> None:
    """Create tables if they do not exist (useful for testing and rapid local boot)."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        if settings.APP_ENV in ("dev", "test"):
            _activate_sqlite_fallback()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        else:
            raise
