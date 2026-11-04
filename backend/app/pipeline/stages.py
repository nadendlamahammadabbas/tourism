"""Idempotent ingestion pipeline stages for Smriti."""

import re
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import StorageBackend
from app.db.models import Asset, Chunk, Extraction, Site
from app.llm.base import LLMClient
from app.logging import logger
from app.pipeline.exif import extract_exif
from app.pipeline.images import create_thumbnail


def chunk_text(text: str, max_words: int = 80, overlap_words: int = 15) -> list[str]:
    """Split text into overlapping chunks of approx token length."""
    words = text.split()
    if not words:
        return []
    if len(words) <= max_words:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end >= len(words):
            break
        start += max_words - overlap_words
    return chunks


async def run_pipeline(
    asset_id: uuid.UUID,
    session: AsyncSession,
    storage: StorageBackend,
    llm_client: LLMClient,
    user_lat: float | None = None,
    user_lng: float | None = None,
    user_site_id: uuid.UUID | None = None,
) -> Asset:
    """Execute all pipeline stages idempotently on an asset."""
    log = logger.bind(asset_id=str(asset_id))
    log.info("pipeline_started")

    # Fetch asset
    stmt = select(Asset).where(Asset.id == asset_id)
    res = await session.execute(stmt)
    asset = res.scalar_one_or_none()
    if not asset:
        raise ValueError(f"Asset not found: {asset_id}")

    try:
        # Stage 1: Validate & Derivatives
        asset.status = "processing"
        asset.stage = "validated"
        asset.stage_updated_at = datetime.utcnow()

        # Read file bytes from storage
        file_bytes = await storage.read(asset.uri)

        # Generate thumbnail if not already present
        if not asset.thumb_uri and asset.mime.startswith("image/"):
            thumb_res = create_thumbnail(file_bytes)
            if thumb_res:
                thumb_bytes, _ = thumb_res
                thumb_key = f"assets/{asset.id}/thumb.webp"
                asset.thumb_uri = await storage.save(thumb_key, thumb_bytes)

        # Extract EXIF if not already present
        if not asset.exif and asset.mime.startswith("image/"):
            exif_data = extract_exif(file_bytes)
            if exif_data:
                asset.exif = exif_data

        await session.commit()
        log.info("stage_validated", has_thumb=bool(asset.thumb_uri), has_exif=bool(asset.exif))

        # Stage 2: Extract (OCR / Vision / Translation / Entities)
        extraction_data = await llm_client.extract_heritage(
            file_bytes=file_bytes,
            mime=asset.mime,
        )

        # Check existing extraction for idempotency
        ext_stmt = select(Extraction).where(Extraction.asset_id == asset.id)
        ext_res = await session.execute(ext_stmt)
        extraction = ext_res.scalar_one_or_none()

        entities_json = [e.model_dump() for e in extraction_data.entities]
        loc_hint_json = extraction_data.location_hint.model_dump() if extraction_data.location_hint else None

        if not extraction:
            extraction = Extraction(
                asset_id=asset.id,
                model="gemini-3.8-flash",
                title=extraction_data.title,
                summary=extraction_data.summary,
                monument_type=extraction_data.monument_type,
                era_estimate=extraction_data.era_estimate,
                features=extraction_data.architectural_features,
                materials=extraction_data.materials,
                language=extraction_data.language,
                script=extraction_data.script,
                transcript=extraction_data.transcript,
                translation_en=extraction_data.translation_en,
                entities=entities_json,
                location_hint=loc_hint_json,
                confidence=extraction_data.confidence,
                uncertainty_notes=extraction_data.uncertainty_notes,
                raw=extraction_data.model_dump(),
            )
            session.add(extraction)
        else:
            extraction.title = extraction_data.title
            extraction.summary = extraction_data.summary
            extraction.monument_type = extraction_data.monument_type
            extraction.era_estimate = extraction_data.era_estimate
            extraction.features = extraction_data.architectural_features
            extraction.materials = extraction_data.materials
            extraction.language = extraction_data.language
            extraction.script = extraction_data.script
            extraction.transcript = extraction_data.transcript
            extraction.translation_en = extraction_data.translation_en
            extraction.entities = entities_json
            extraction.location_hint = loc_hint_json
            extraction.confidence = extraction_data.confidence
            extraction.uncertainty_notes = extraction_data.uncertainty_notes
            extraction.raw = extraction_data.model_dump()

        asset.stage = "extracted"
        asset.stage_updated_at = datetime.utcnow()
        await session.commit()
        log.info("stage_extracted", title=extraction_data.title)

        # Stage 3: Embed (Chunk & gemini-embedding-2)
        # Delete prior chunks for idempotency
        del_stmt = select(Chunk).where(Chunk.asset_id == asset.id)
        existing_chunks = (await session.execute(del_stmt)).scalars().all()
        for c in existing_chunks:
            await session.delete(c)

        text_to_embed = " ".join(filter(None, [
            extraction_data.title,
            extraction_data.summary,
            extraction_data.transcript,
            extraction_data.translation_en,
            " ".join(extraction_data.architectural_features),
        ]))

        chunks_text = chunk_text(text_to_embed)
        for idx, chunk_str in enumerate(chunks_text):
            vec = await llm_client.embed_text(chunk_str)
            chunk_record = Chunk(
                asset_id=asset.id,
                site_id=user_site_id or asset.site_id,
                chunk_index=idx,
                text=chunk_str,
                embedding=vec,
                tsv=chunk_str.lower(),
            )
            session.add(chunk_record)

        asset.stage = "embedded"
        asset.stage_updated_at = datetime.utcnow()
        await session.commit()
        log.info("stage_embedded", chunk_count=len(chunks_text))

        # Stage 4: Locate (Precedence: user > EXIF > model > unplaced)
        final_lat = user_lat
        final_lng = user_lng
        loc_source = "user" if (user_lat is not None and user_lng is not None) else None

        if final_lat is None and asset.exif and "gps" in asset.exif:
            gps = asset.exif["gps"]
            if "lat" in gps and "lng" in gps:
                final_lat = float(gps["lat"])
                final_lng = float(gps["lng"])
                loc_source = "exif"

        if final_lat is None and extraction_data.location_hint and extraction_data.location_hint.lat:
            final_lat = extraction_data.location_hint.lat
            final_lng = extraction_data.location_hint.lng
            loc_source = "model"

        # Resolve or create site
        site_id = user_site_id or asset.site_id
        if not site_id and (extraction_data.site_name or final_lat is not None):
            site_name = extraction_data.site_name or extraction_data.title or "Heritage Site"
            base_slug = re.sub(r"[^\w\s-]", "", site_name.lower()).replace(" ", "-")
            slug = f"{base_slug}-{str(asset.id)[:8]}"

            site = Site(
                slug=slug,
                name=site_name,
                type=extraction_data.monument_type or "other",
                era_label=extraction_data.era_estimate,
                lat=final_lat,
                lng=final_lng,
                location_source=loc_source or "model",
                description=extraction_data.summary,
                cover_asset_id=asset.id,
            )
            session.add(site)
            await session.flush()
            site_id = site.id
            asset.site_id = site_id

        asset.stage = "located"
        asset.stage_updated_at = datetime.utcnow()
        await session.commit()
        log.info("stage_located", lat=final_lat, lng=final_lng, source=loc_source)

        # Stage 5: Done
        asset.stage = "done"
        asset.status = "done"
        asset.error = None
        asset.stage_updated_at = datetime.utcnow()
        await session.commit()
        log.info("pipeline_completed")

    except Exception as e:
        log.error("pipeline_failed", error=str(e))
        asset.status = "failed"
        asset.error = str(e)
        asset.stage_updated_at = datetime.utcnow()
        await session.commit()
        raise

    return asset
