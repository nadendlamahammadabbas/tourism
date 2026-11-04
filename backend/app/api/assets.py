"""Asset upload, retrieval, and SSE event streaming endpoints."""

import asyncio
import hashlib
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import sanitize_filename, validate_magic_bytes, verify_contributor_token
from app.core.storage import StorageBackend
from app.db.models import Asset, Extraction, Job
from app.deps import get_db_session, get_storage
from app.logging import logger

router = APIRouter(prefix="/assets", tags=["Assets"])


class AssetResponse(BaseModel):
    id: str
    site_id: str | None
    kind: str
    sha256: str
    mime: str
    bytes: int
    stage: str
    status: str
    error: str | None
    created_at: str
    extraction: dict[str, Any] | None = None


class ExtractionUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    transcript: str | None = None
    translation_en: str | None = None
    monument_type: str | None = None
    era_estimate: str | None = None


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload_asset(
    file: UploadFile = File(...),
    site_id: str | None = Form(default=None),
    title: str | None = Form(default=None),
    lat: float | None = Form(default=None),
    lng: float | None = Form(default=None),
    notes: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db_session),
    storage: StorageBackend = Depends(get_storage),
    _: str = Depends(verify_contributor_token),
) -> dict[str, Any]:
    """Upload photo, manuscript scan, or journal page for asynchronous ingestion."""
    contents = await file.read()
    clean_name = sanitize_filename(file.filename or "upload")
    mime, ext = validate_magic_bytes(contents, clean_name)
    file_sha256 = hashlib.sha256(contents).hexdigest()

    # Check for duplicate asset (idempotency)
    stmt = select(Asset).where(Asset.sha256 == file_sha256)
    res = await session.execute(stmt)
    existing_asset = res.scalar_one_or_none()

    if existing_asset:
        logger.info("duplicate_asset_uploaded", asset_id=str(existing_asset.id), sha256=file_sha256)
        return {
            "asset_id": str(existing_asset.id),
            "status": existing_asset.status,
            "stage": existing_asset.stage,
            "message": "Asset already exists (deduplicated by sha256)",
            "is_duplicate": True,
        }

    # Store file
    asset_id = uuid.uuid4()
    storage_key = f"assets/{asset_id}/{clean_name}"
    uri = await storage.save(storage_key, contents)

    # Determine kind
    kind = "document" if mime == "application/pdf" else "photo"

    # Create Asset record
    asset = Asset(
        id=asset_id,
        site_id=uuid.UUID(site_id) if site_id else None,
        kind=kind,
        uri=uri,
        sha256=file_sha256,
        mime=mime,
        bytes=len(contents),
        stage="queued",
        status="queued",
    )
    session.add(asset)

    # Enqueue Ingestion Job
    job = Job(
        kind="ingest_asset",
        payload={
            "asset_id": str(asset_id),
            "site_id": site_id,
            "title": title,
            "lat": lat,
            "lng": lng,
            "notes": notes,
        },
        status="queued",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    logger.info("asset_enqueued", asset_id=str(asset_id), job_id=job.id)

    return {
        "asset_id": str(asset_id),
        "job_id": job.id,
        "status": "queued",
        "stage": "queued",
        "is_duplicate": False,
    }


@router.get("/{asset_id}")
async def get_asset(
    asset_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve asset details, extraction, and current pipeline stage."""
    try:
        uid = uuid.UUID(asset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid asset UUID") from None

    stmt = select(Asset).where(Asset.id == uid)
    res = await session.execute(stmt)
    asset = res.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    ext_stmt = select(Extraction).where(Extraction.asset_id == uid)
    ext_res = await session.execute(ext_stmt)
    extraction = ext_res.scalar_one_or_none()

    extraction_dict = None
    if extraction:
        extraction_dict = {
            "title": extraction.title,
            "summary": extraction.summary,
            "monument_type": extraction.monument_type,
            "era_estimate": extraction.era_estimate,
            "features": extraction.features,
            "materials": extraction.materials,
            "language": extraction.language,
            "script": extraction.script,
            "transcript": extraction.transcript,
            "translation_en": extraction.translation_en,
            "entities": extraction.entities,
            "location_hint": extraction.location_hint,
            "confidence": extraction.confidence,
            "uncertainty_notes": extraction.uncertainty_notes,
            "edited_by_human": extraction.edited_by_human,
        }

    return {
        "id": str(asset.id),
        "site_id": str(asset.site_id) if asset.site_id else None,
        "kind": asset.kind,
        "uri": asset.uri,
        "thumb_uri": asset.thumb_uri,
        "depth_uri": asset.depth_uri,
        "sha256": asset.sha256,
        "mime": asset.mime,
        "bytes": asset.bytes,
        "stage": asset.stage,
        "status": asset.status,
        "error": asset.error,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
        "extraction": extraction_dict,
    }


@router.get("/{asset_id}/events")
async def stream_asset_events(
    asset_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Stream Server-Sent Events (SSE) tracking pipeline stage progress."""
    try:
        uid = uuid.UUID(asset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid asset UUID") from None

    async def event_generator():
        last_stage = None
        for _ in range(60):  # Stream for up to 60 seconds
            stmt = select(Asset).where(Asset.id == uid)
            res = await session.execute(stmt)
            asset = res.scalar_one_or_none()

            if asset:
                if asset.stage != last_stage or asset.status in ("done", "failed"):
                    last_stage = asset.stage
                    payload = {
                        "asset_id": str(asset.id),
                        "stage": asset.stage,
                        "status": asset.status,
                        "error": asset.error,
                    }
                    yield f"event: stage_change\ndata: {json.dumps(payload)}\n\n"

                if asset.status in ("done", "failed"):
                    break

            await asyncio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.patch("/extractions/{asset_id}")
async def patch_extraction(
    asset_id: str,
    update_data: ExtractionUpdate,
    session: AsyncSession = Depends(get_db_session),
    _: str = Depends(verify_contributor_token),
) -> dict[str, Any]:
    """Human-in-the-loop correction of extracted text, translation, or metadata."""
    try:
        uid = uuid.UUID(asset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid asset UUID") from None

    stmt = select(Extraction).where(Extraction.asset_id == uid)
    res = await session.execute(stmt)
    extraction = res.scalar_one_or_none()
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found for asset")

    # Apply updates
    if update_data.title is not None:
        extraction.title = update_data.title
    if update_data.summary is not None:
        extraction.summary = update_data.summary
    if update_data.transcript is not None:
        extraction.transcript = update_data.transcript
    if update_data.translation_en is not None:
        extraction.translation_en = update_data.translation_en
    if update_data.monument_type is not None:
        extraction.monument_type = update_data.monument_type
    if update_data.era_estimate is not None:
        extraction.era_estimate = update_data.era_estimate

    extraction.edited_by_human = True
    await session.commit()

    return {"status": "updated", "asset_id": asset_id, "edited_by_human": True}

