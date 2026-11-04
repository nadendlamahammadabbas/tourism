"""Security utilities: contributor token validation, magic byte inspection, path sanitization."""

import re
from pathlib import Path

import filetype
from fastapi import Header, HTTPException, status

from app.config import settings

ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}

MAX_FILE_BYTES = 15 * 1024 * 1024  # 15 MB


def verify_contributor_token(
    x_contributor_token: str | None = Header(default=None, alias="X-Contributor-Token"),
) -> str:
    """Ensure the request carries the required contributor token for write operations."""
    # In dev or test mode with empty token, allow pass-through
    if settings.APP_ENV in ("dev", "test") and not settings.CONTRIBUTOR_TOKEN:
        return "dev-contributor"

    if not x_contributor_token or x_contributor_token != settings.CONTRIBUTOR_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-Contributor-Token header",
        )
    return x_contributor_token


def sanitize_filename(filename: str) -> str:
    """Sanitize uploaded filename against path traversal and special characters."""
    base = Path(filename).name
    # Strip dangerous characters
    cleaned = re.sub(r"[^\w\s\.-]", "", base).strip()
    return cleaned or "unnamed_asset"


def validate_magic_bytes(file_bytes: bytes, original_filename: str) -> tuple[str, str]:
    """Validate file content by inspecting magic bytes. Returns (mime_type, extension)."""
    if len(file_bytes) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of 15MB (got {len(file_bytes)} bytes)",
        )

    kind = filetype.guess(file_bytes)
    mime = kind.mime if kind else None

    # Fallback check for standard PDF headers if filetype missed it
    if not mime and file_bytes.startswith(b"%PDF-"):
        mime = "application/pdf"

    if not mime or mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file format '{mime}'. Smriti accepts JPEG, PNG, WebP, and PDF.",
        )

    return mime, ALLOWED_MIME_TYPES[mime]

