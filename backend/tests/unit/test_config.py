"""Unit tests for configuration loading."""

from app.config import Settings


def test_default_config():
    settings = Settings()
    assert settings.APP_ENV in ("dev", "test", "prod")
    assert settings.EMBED_DIM == 768
    assert "gemini" in settings.GEMINI_MODEL
    assert len(settings.cors_origin_list) > 0


def test_cors_origins_parsing():
    s = Settings(CORS_ORIGINS="http://localhost:3000, https://smriti.org")
    assert s.cors_origin_list == ["http://localhost:3000", "https://smriti.org"]

