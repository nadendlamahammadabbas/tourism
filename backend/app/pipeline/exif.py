"""EXIF metadata extraction and privacy sanitization."""

import io
from typing import Any

from PIL import ExifTags, Image


def _convert_to_degrees(value: Any) -> float | None:
    """Helper function to convert GPS coordinates stored in EXIF format to degrees in float."""
    try:
        if isinstance(value, (tuple, list)) and len(value) == 3:
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60.0) + (s / 3600.0)
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def extract_exif(file_bytes: bytes) -> dict[str, Any] | None:
    """Extract raw EXIF dictionary including decimal GPS coordinates from JPEG/TIFF image."""
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            raw_exif = img.getexif()
            if not raw_exif:
                return None

            exif_dict: dict[str, Any] = {}
            for tag_id, val in raw_exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                # Skip large binary blobs or unencodable types
                if isinstance(val, (bytes, bytearray)):
                    continue
                exif_dict[tag_name] = str(val)

            # Check IFD GPSInfo
            gps_info = raw_exif.get_ifd(ExifTags.IFD.GPSInfo)
            if gps_info:
                lat_raw = gps_info.get(ExifTags.GPS.GPSLatitude)
                lat_ref = gps_info.get(ExifTags.GPS.GPSLatitudeRef)
                lng_raw = gps_info.get(ExifTags.GPS.GPSLongitude)
                lng_ref = gps_info.get(ExifTags.GPS.GPSLongitudeRef)

                lat = _convert_to_degrees(lat_raw)
                lng = _convert_to_degrees(lng_raw)

                if lat is not None and lat_ref in ("S", "s"):
                    lat = -lat
                if lng is not None and lng_ref in ("W", "w"):
                    lng = -lng

                if lat is not None and lng is not None:
                    exif_dict["gps"] = {
                        "lat": round(lat, 6),
                        "lng": round(lng, 6),
                        "lat_ref": str(lat_ref),
                        "lng_ref": str(lng_ref),
                    }

            return exif_dict if exif_dict else None
    except Exception:
        return None


def strip_exif(file_bytes: bytes) -> bytes:
    """Strip EXIF data from image bytes to protect private GPS info on public derivatives."""
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            # Saving without passing exif parameter strips all EXIF metadata
            buf = io.BytesIO()
            fmt = img.format if img.format else "JPEG"
            if img.mode in ("RGBA", "LA") and fmt.upper() in ("JPEG", "JPG"):
                img = img.convert("RGB")
            img.save(buf, format=fmt)
            return buf.getvalue()
    except Exception:
        return file_bytes
