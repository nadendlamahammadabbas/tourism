"""Integration tests for routes and stories endpoints."""

import pytest

from app.db.models import Route, Site, Story


@pytest.mark.asyncio
async def test_routes_and_stories_endpoints(client, db_session):
    # Setup site
    site = Site(
        slug="test-stepwell",
        name="Test Stepwell",
        type="stepwell",
        lat=23.5,
        lng=72.5,
    )
    db_session.add(site)
    await db_session.flush()

    # Setup route
    route = Route(
        name="Test Stepwell Trail",
        description="A journey through test stepwells",
        stop_site_ids=[str(site.id)],
    )
    db_session.add(route)

    # Setup story
    story = Story(
        site_id=site.id,
        kind="folklore",
        title="Legend of the Ancient Reservoir",
        body="Folklore states that the water never dried up even during the great drought.",
    )
    db_session.add(story)
    await db_session.commit()

    # Test GET /api/v1/routes
    r_resp = await client.get("/api/v1/routes")
    assert r_resp.status_code == 200
    r_data = r_resp.json()
    assert len(r_data) >= 1
    assert r_data[0]["name"] == "Test Stepwell Trail"
    assert len(r_data[0]["stops"]) == 1

    # Test GET /api/v1/stories
    s_resp = await client.get("/api/v1/stories")
    assert s_resp.status_code == 200
    s_data = s_resp.json()
    assert len(s_data) >= 1
    assert s_data[0]["title"] == "Legend of the Ancient Reservoir"
    assert s_data[0]["site_slug"] == "test-stepwell"
