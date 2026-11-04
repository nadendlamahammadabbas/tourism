"""Integration tests verifying end-to-end pipeline stage progression."""

import hashlib
import uuid

import pytest
from sqlalchemy import select

from app.db.models import Asset, Chunk, Extraction, Site
from app.pipeline.stages import run_pipeline


@pytest.mark.asyncio
async def test_pipeline_progression(db_session, temp_storage, fake_llm):
    # Setup test asset
    sample_data = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"image-payload"
    sha = hashlib.sha256(sample_data).hexdigest()
    uri = await temp_storage.save("test/stepwell.jpg", sample_data)

    asset = Asset(
        id=uuid.uuid4(),
        uri=uri,
        sha256=sha,
        mime="image/jpeg",
        bytes=len(sample_data),
        kind="photo",
        stage="queued",
        status="queued",
    )
    db_session.add(asset)
    await db_session.commit()

    # Run pipeline
    processed_asset = await run_pipeline(
        asset_id=asset.id,
        session=db_session,
        storage=temp_storage,
        llm_client=fake_llm,
        user_lat=23.8589,
        user_lng=72.1017,
    )

    assert processed_asset.status == "done"
    assert processed_asset.stage == "done"

    # Verify extraction record
    ext_stmt = select(Extraction).where(Extraction.asset_id == asset.id)
    ext = (await db_session.execute(ext_stmt)).scalar_one_or_none()
    assert ext is not None
    assert ext.title is not None
    assert ext.confidence is not None

    # Verify chunk records
    chunk_stmt = select(Chunk).where(Chunk.asset_id == asset.id)
    chunks = (await db_session.execute(chunk_stmt)).scalars().all()
    assert len(chunks) > 0
    assert len(chunks[0].embedding) == 768

    # Verify site created
    site_stmt = select(Site).where(Site.id == processed_asset.site_id)
    site = (await db_session.execute(site_stmt)).scalar_one_or_none()
    assert site is not None
    assert site.lat == 23.8589
    assert site.lng == 72.1017

