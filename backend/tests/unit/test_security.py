"""Unit tests for magic bytes and security validation."""

import pytest
from fastapi import HTTPException

from app.core.security import sanitize_filename, validate_magic_bytes


def test_sanitize_filename():
    assert sanitize_filename("../../malicious.png") == "malicious.png"
    assert sanitize_filename("safe_photo-123.jpg") == "safe_photo-123.jpg"
    assert sanitize_filename("weird!@#$%^&*()_+name.webp") == "weird_name.webp"


def test_validate_magic_bytes_jpeg():
    # JPEG magic bytes header: FF D8 FF
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"\x00" * 100
    mime, ext = validate_magic_bytes(jpeg_bytes, "test.jpg")
    assert mime == "image/jpeg"
    assert ext == ".jpg"


def test_validate_magic_bytes_pdf():
    pdf_bytes = b"%PDF-1.4 header contents and trailer %%EOF"
    mime, ext = validate_magic_bytes(pdf_bytes, "doc.pdf")
    assert mime == "application/pdf"
    assert ext == ".pdf"


def test_validate_magic_bytes_invalid():
    with pytest.raises(HTTPException) as exc_info:
        validate_magic_bytes(b"PLAIN TEXT NOT ALLOWED", "notes.txt")
    assert exc_info.value.status_code == 415

