"""Unit tests verifying FakeClient extraction schema and embeddings."""

import math

import pytest

from app.llm.fake import FakeClient


@pytest.mark.asyncio
async def test_fake_extraction_photo():
    client = FakeClient()
    sample_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 200
    ext = await client.extract_heritage(sample_bytes, "image/jpeg")

    assert ext.kind in ("photo", "document")
    assert ext.title
    assert ext.summary
    assert ext.monument_type
    assert 0.0 <= ext.confidence <= 1.0
    assert ext.location_hint is not None


@pytest.mark.asyncio
async def test_fake_embedding_dimensions_and_normalization():
    client = FakeClient()
    vec = await client.embed_text("Rani ki Vav Stepwell in Patan")

    assert len(vec) == 768
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-4


@pytest.mark.asyncio
async def test_fake_cited_ask():
    client = FakeClient()
    sources = [{"asset_id": "test-uuid", "text": "Detailed history of stepwells in Gujarat"}]
    res = await client.ask_archive("Tell me about stepwells", sources)

    assert "citations" in res
    assert len(res["citations"]) > 0
    assert "[1]" in res["answer"]

