"""Image processing utilities: downscaling, thumbnail generation, and format conversion."""

import io

from PIL import Image


def downscale_image(file_bytes: bytes, max_long_edge: int = 2048) -> bytes:
    """Downscale image if its longest edge exceeds max_long_edge (maintaining aspect ratio)."""
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            w, h = img.size
            if max(w, h) <= max_long_edge:
                return file_bytes

            scale = max_long_edge / max(w, h)
            new_w = int(w * scale)
            new_h = int(h * scale)

            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            fmt = img.format if img.format else "JPEG"
            if fmt.upper() in ("JPEG", "JPG"):
                resized.convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
            elif fmt.upper() == "PNG":
                resized.save(buf, format="PNG", optimize=True)
            elif fmt.upper() == "WEBP":
                resized.save(buf, format="WEBP", quality=85)
            else:
                resized.convert("RGB").save(buf, format="JPEG", quality=85)
            return buf.getvalue()
    except Exception:
        return file_bytes


def create_thumbnail(file_bytes: bytes, max_dim: int = 400) -> tuple[bytes, str] | None:
    """Generate an optimized WebP thumbnail. Returns (thumbnail_bytes, mime_type)."""
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            img = img.convert("RGB")
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=80)
            return buf.getvalue(), "image/webp"
    except Exception:
        return None
