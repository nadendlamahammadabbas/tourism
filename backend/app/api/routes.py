"""Routes and Stories query endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Route, Site, Story
from app.deps import get_db_session

router = APIRouter(tags=["Routes & Stories"])


@router.get("/routes")
async def list_routes(
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Retrieve curated heritage travel itineraries with polyline stop coordinates."""
    stmt = select(Route)
    res = await session.execute(stmt)
    routes = res.scalars().all()

    # Pre-fetch all sites to assemble stops in memory
    all_sites_res = await session.execute(select(Site))
    sites_by_id = {str(s.id): s for s in all_sites_res.scalars().all()}

    output = []
    for r in routes:
        stop_ids = r.stop_site_ids or []
        stops = []
        coordinates = []

        for sid in stop_ids:
            site = sites_by_id.get(str(sid))
            if site:
                stops.append({
                    "id": str(site.id),
                    "slug": site.slug,
                    "name": site.name,
                    "type": site.type,
                    "lat": site.lat,
                    "lng": site.lng,
                    "era_label": site.era_label,
                })
                if site.lng is not None and site.lat is not None:
                    coordinates.append([site.lng, site.lat])

        # Generate GeoJSON LineString geometry
        line_geometry = (
            {"type": "LineString", "coordinates": coordinates} if len(coordinates) >= 2 else None
        )

        output.append({
            "id": str(r.id),
            "name": r.name,
            "description": r.description,
            "geometry": line_geometry,
            "stops": stops,
            "stop_count": len(stops),
        })

    return output


@router.get("/stories")
async def list_stories(
    site_id: str | None = Query(default=None, description="Optional site UUID to filter stories"),
    kind: str | None = Query(default=None, description="folklore | observation | journal"),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Retrieve historical folklore, epigraphic observations, and travel journals."""
    stmt = select(Story, Site.name.label("site_name"), Site.slug.label("site_slug"), Site.lat, Site.lng).join(
        Site, Story.site_id == Site.id
    )

    if site_id:
        try:
            uid = uuid.UUID(site_id)
            stmt = stmt.where(Story.site_id == uid)
        except ValueError:
            stmt = stmt.where(Site.slug == site_id)

    if kind:
        stmt = stmt.where(Story.kind == kind)

    res = await session.execute(stmt)
    rows = res.all()

    output = []
    for story, site_name, site_slug, lat, lng in rows:
        output.append({
            "id": str(story.id),
            "site_id": str(story.site_id),
            "site_name": site_name,
            "site_slug": site_slug,
            "lat": lat,
            "lng": lng,
            "kind": story.kind,
            "title": story.title,
            "body": story.body,
            "source_asset_id": str(story.source_asset_id) if story.source_asset_id else None,
        })

    return output
