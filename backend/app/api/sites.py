"""Site query and GeoJSON serialization endpoints for the Atlas map."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Asset, Site
from app.deps import get_db_session

router = APIRouter(prefix="/sites", tags=["Sites"])


@router.get("")
async def list_sites(
    bbox: str | None = Query(default=None, description="minLng,minLat,maxLng,maxLat"),
    type: str | None = Query(default=None, description="Site monument type filter"),
    era_from: int | None = Query(default=None, description="Start year CE"),
    era_to: int | None = Query(default=None, description="End year CE"),
    q: str | None = Query(default=None, description="Search term"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve heritage sites formatted as a GeoJSON FeatureCollection."""
    stmt = select(Site)

    if type:
        stmt = stmt.where(Site.type == type)
    if era_from is not None:
        stmt = stmt.where(Site.era_start >= era_from)
    if era_to is not None:
        stmt = stmt.where(Site.era_end <= era_to)
    if q:
        stmt = stmt.where(Site.name.ilike(f"%{q}%"))

    # Parse bbox if provided
    if bbox:
        try:
            min_lng, min_lat, max_lng, max_lat = map(float, bbox.split(","))
            stmt = stmt.where(
                Site.lng >= min_lng,
                Site.lng <= max_lng,
                Site.lat >= min_lat,
                Site.lat <= max_lat,
            )
        except ValueError:
            pass

    res = await session.execute(stmt)
    sites = res.scalars().all()

    features = []
    for s in sites:
        if s.lng is not None and s.lat is not None:
            geometry = {
                "type": "Point",
                "coordinates": [s.lng, s.lat],
            }
        else:
            geometry = None

        features.append({
            "type": "Feature",
            "id": str(s.id),
            "geometry": geometry,
            "properties": {
                "id": str(s.id),
                "slug": s.slug,
                "name": s.name,
                "name_local": s.name_local,
                "type": s.type,
                "era_label": s.era_label,
                "era_start": s.era_start,
                "era_end": s.era_end,
                "region": s.region,
                "state": s.state,
                "location_source": s.location_source,
                "description": s.description,
                "cover_asset_id": str(s.cover_asset_id) if s.cover_asset_id else None,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get("/{site_id}")
async def get_site(
    site_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve comprehensive site detail with linked assets, extractions, and stories."""
    try:
        uid = uuid.UUID(site_id)
        stmt = select(Site).where(Site.id == uid)
    except ValueError:
        stmt = select(Site).where(Site.slug == site_id)

    stmt = stmt.options(
        selectinload(Site.assets).selectinload(Asset.extraction),
        selectinload(Site.stories),
    )
    res = await session.execute(stmt)
    site = res.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    assets_data = []
    for a in site.assets:
        ext_dict = None
        if a.extraction:
            ext_dict = {
                "title": a.extraction.title,
                "summary": a.extraction.summary,
                "transcript": a.extraction.transcript,
                "translation_en": a.extraction.translation_en,
                "confidence": a.extraction.confidence,
                "entities": a.extraction.entities,
            }
        assets_data.append({
            "id": str(a.id),
            "kind": a.kind,
            "uri": a.uri,
            "thumb_uri": a.thumb_uri,
            "depth_uri": a.depth_uri,
            "sha256": a.sha256,
            "extraction": ext_dict,
        })

    stories_data = [
        {
            "id": str(st.id),
            "kind": st.kind,
            "title": st.title,
            "body": st.body,
        }
        for st in site.stories
    ]

    return {
        "id": str(site.id),
        "slug": site.slug,
        "name": site.name,
        "name_local": site.name_local,
        "type": site.type,
        "era_label": site.era_label,
        "era_start": site.era_start,
        "era_end": site.era_end,
        "region": site.region,
        "state": site.state,
        "lat": site.lat,
        "lng": site.lng,
        "location_source": site.location_source,
        "description": site.description,
        "cover_asset_id": str(site.cover_asset_id) if site.cover_asset_id else None,
        "assets": assets_data,
        "stories": stories_data,
    }

