"""Unit tests for storage backend."""

import pytest

from app.core.storage import LocalStorageBackend


@pytest.mark.asyncio
async def test_storage_save_and_read(tmp_path):
    storage = LocalStorageBackend(base_dir=tmp_path)
    test_data = b"heritage image binary content"
    uri = await storage.save("test/file.jpg", test_data)

    assert await storage.exists(uri)
    read_data = await storage.read(uri)
    assert read_data == test_data

    deleted = await storage.delete(uri)
    assert deleted is True
    assert not await storage.exists(uri)


@pytest.mark.asyncio
async def test_storage_path_traversal_prevention(tmp_path):
    storage = LocalStorageBackend(base_dir=tmp_path)
    with pytest.raises(ValueError, match="Path traversal"):
        await storage.save("../../../etc/passwd", b"bad")

