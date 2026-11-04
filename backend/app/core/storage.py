"""Storage backend abstraction and local filesystem implementation."""

from abc import ABC, abstractmethod
from pathlib import Path

import aiofiles

from app.config import settings


class StorageBackend(ABC):
    """Abstract interface for storing and retrieving raw archive assets and derivatives."""

    @abstractmethod
    async def save(self, key: str, data: bytes) -> str:
        """Save bytes under key. Returns uri."""
        pass

    @abstractmethod
    async def read(self, uri: str) -> bytes:
        """Read bytes by uri."""
        pass

    @abstractmethod
    async def exists(self, uri: str) -> bool:
        """Check if asset exists."""
        pass

    @abstractmethod
    async def delete(self, uri: str) -> bool:
        """Delete asset by uri."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local disk storage implementation storing assets in configured STORAGE_DIR."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else settings.storage_path
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, uri_or_key: str) -> Path:
        # Strip file:// prefix if present
        cleaned = uri_or_key.replace("file://", "").lstrip("/\\")
        p = (self.base_dir / cleaned).resolve()
        # Security: Prevent directory traversal outside base_dir
        if not str(p).startswith(str(self.base_dir.resolve())):
            raise ValueError(f"Path traversal detected: {uri_or_key}")
        return p

    async def save(self, key: str, data: bytes) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        return str(path.as_posix())

    async def read(self, uri: str) -> bytes:
        path = self._resolve(uri)
        if not path.exists():
            raise FileNotFoundError(f"Asset not found at {uri}")
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def exists(self, uri: str) -> bool:
        try:
            return self._resolve(uri).exists()
        except ValueError:
            return False

    async def delete(self, uri: str) -> bool:
        try:
            p = self._resolve(uri)
            if p.exists():
                p.unlink()
                return True
        except (ValueError, OSError):
            pass
        return False

