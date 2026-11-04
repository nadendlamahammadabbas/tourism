"""Integration tests for asset endpoints and duplicate deduplication."""

import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_upload_asset_and_duplicate(client):
    # Minimal JPEG bytes
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00" + b"\x00" * 200

    headers = {"X-Contributor-Token": "test-token"}
    files = {"file": ("stepwell_sample.jpg", jpeg_bytes, "image/jpeg")}
    data = {"title": "Adalaj Stepwell Pavilion", "lat": "23.1667", "lng": "72.5833"}

    # First upload
    response = await client.post("/api/v1/assets", files=files, data=data, headers=headers)
    assert response.status_code == 202
    resp_json = response.json()
    assert resp_json["status"] == "queued"
    assert resp_json["is_duplicate"] is False
    asset_id = resp_json["asset_id"]

    # Duplicate upload with identical contents
    dup_files = {"file": ("stepwell_sample.jpg", jpeg_bytes, "image/jpeg")}
    dup_response = await client.post("/api/v1/assets", files=dup_files, data=data, headers=headers)
    assert dup_response.status_code == 202
    dup_json = dup_response.json()
    assert dup_json["asset_id"] == asset_id
    assert dup_json["is_duplicate"] is True

    # Get asset details
    get_res = await client.get(f"/api/v1/assets/{asset_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == asset_id

