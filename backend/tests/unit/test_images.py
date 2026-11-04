"""Unit tests for image downscaling and thumbnail generation."""

import io

from PIL import Image

from app.pipeline.images import create_thumbnail, downscale_image


def test_downscale_large_image():
    # Create large 3000x1500 image
    img = Image.new("RGB", (3000, 1500), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    large_bytes = buf.getvalue()

    downscaled = downscale_image(large_bytes, max_long_edge=2048)
    with Image.open(io.BytesIO(downscaled)) as result_img:
        w, h = result_img.size
        assert max(w, h) <= 2048
        assert w == 2048
        assert h == 1024


def test_downscale_small_image_unchanged():
    img = Image.new("RGB", (800, 600), color="yellow")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    small_bytes = buf.getvalue()

    result = downscale_image(small_bytes, max_long_edge=2048)
    with Image.open(io.BytesIO(result)) as result_img:
        assert result_img.size == (800, 600)


def test_create_thumbnail():
    img = Image.new("RGB", (1200, 900), color="purple")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    thumb_res = create_thumbnail(buf.getvalue(), max_dim=400)
    assert thumb_res is not None
    thumb_bytes, mime = thumb_res
    assert mime == "image/webp"

    with Image.open(io.BytesIO(thumb_bytes)) as thumb_img:
        w, h = thumb_img.size
        assert max(w, h) <= 400
