"""Unit tests for EXIF metadata extraction and privacy sanitization."""

import io

from PIL import Image

from app.pipeline.exif import _convert_to_degrees, extract_exif, strip_exif


def test_convert_to_degrees():
    assert _convert_to_degrees(23.5) == 23.5
    # (degrees, minutes, seconds)
    dms = (23.0, 10.0, 30.0)
    expected = 23.0 + (10.0 / 60.0) + (30.0 / 3600.0)
    assert abs(_convert_to_degrees(dms) - expected) < 1e-6
    assert _convert_to_degrees(None) is None


def test_strip_exif():
    # Create simple image in memory
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    raw_bytes = buf.getvalue()

    cleaned = strip_exif(raw_bytes)
    assert len(cleaned) > 0
    # Cleaned image should open properly without errors
    with Image.open(io.BytesIO(cleaned)) as verify_img:
        assert verify_img.size == (100, 100)


def test_extract_exif_no_tags():
    img = Image.new("RGB", (50, 50), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    res = extract_exif(buf.getvalue())
    assert res is None or "gps" not in res
