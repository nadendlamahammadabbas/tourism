"""Unit tests for GeminiClient fallback and schema handling."""

import io

import pytest
from PIL import Image

from app.llm.gemini import GeminiClient


@pytest.mark.asyncio
async def test_gemini_client_fallback_to_fake_when_no_key():
    # Instantiate without key
    client = GeminiClient(api_key=None)

    img = Image.new("RGB", (200, 200), color="orange")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    ext = await client.extract_heritage(buf.getvalue(), "image/jpeg")
    assert ext.title
    assert ext.monument_type
    assert ext.confidence > 0.0

    vec = await client.embed_text("Sun Temple Modhera")
    assert len(vec) == 768

    ask = await client.ask_archive("Tell me about Modhera", [{"asset_id": "1", "text": "Sun temple in Gujarat"}])
    assert "answer" in ask
    assert len(ask["citations"]) > 0
