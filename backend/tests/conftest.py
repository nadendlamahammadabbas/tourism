"""Pytest configuration and async test fixtures."""

import os
import tempfile
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Force test environment variables before app imports
os.environ["APP_ENV"] = "test"
os.environ["LLM_MODE"] = "fake"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["CONTRIBUTOR_TOKEN"] = "test-token"

from app.core.storage import LocalStorageBackend, StorageBackend
from app.db.models import Base
from app.deps import get_db_session, get_storage
from app.llm.fake import FakeClient
from app.main import app

test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session", autouse=True)
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def temp_storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageBackend(base_dir=tmpdir)
        yield storage


@pytest.fixture(scope="function")
def fake_llm():
    return FakeClient()


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession, temp_storage: StorageBackend) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    def override_get_storage():
        return temp_storage

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_storage] = override_get_storage

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()

