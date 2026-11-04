"""Dependency injection providers for FastAPI routes."""

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.core.storage import LocalStorageBackend, StorageBackend
from app.db.session import AsyncSessionLocal
from app.llm.base import LLMClient
from app.llm.fake import FakeClient


@lru_cache
def get_settings() -> Settings:
    return settings


@lru_cache
def get_storage() -> StorageBackend:
    return LocalStorageBackend()


@lru_cache
def get_llm_client() -> LLMClient:
    # In fake mode, use deterministic FakeClient
    if settings.LLM_MODE == "fake" or not settings.GEMINI_API_KEY:
        return FakeClient()
    # In live mode, instantiate GeminiClient (to be deepened in Phase 2)
    from app.llm.gemini import GeminiClient
    return GeminiClient()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

