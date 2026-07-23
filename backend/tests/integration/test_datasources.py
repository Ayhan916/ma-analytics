"""Integration tests for /datasources endpoints."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_list_datasources_requires_auth(client: AsyncClient):
    resp = await client.get("/datasources")
    assert resp.status_code == 401


async def test_list_datasources_empty_for_new_user(logged_in_client: AsyncClient):
    resp = await logged_in_client.get("/datasources")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_google_play_datasource(logged_in_client: AsyncClient):
    with patch("app.pipeline.tasks.scrape_and_run") as mock_task:
        mock_task.delay = MagicMock()
        resp = await logged_in_client.post("/datasources/google-play", json={
            "name": "Test App",
            "app_id": "com.test.app",
            "count": 100,
            "lang": "de",
            "country": "de",
        })
    assert resp.status_code == 201
    body = resp.json()
    assert body["app_id"] == "com.test.app"
    assert body["scrape_lang"] == "de"
    assert body["job_status"] == "pending"


async def test_create_google_play_invalid_app_id(logged_in_client: AsyncClient):
    resp = await logged_in_client.post("/datasources/google-play", json={
        "name": "Bad App",
        "app_id": "invalid app id with spaces",
        "count": 100,
    })
    assert resp.status_code == 422


async def test_create_google_play_count_is_capped(logged_in_client: AsyncClient):
    with patch("app.pipeline.tasks.scrape_and_run") as mock_task:
        mock_task.delay = MagicMock()
        resp = await logged_in_client.post("/datasources/google-play", json={
            "name": "Big App",
            "app_id": "com.big.app",
            "count": 9999999,
        })
    assert resp.status_code == 201
    # scrape_count must not exceed SCRAPE_MAX_REVIEWS
    assert resp.json()["scrape_count"] <= 50000


async def test_delete_datasource(logged_in_client: AsyncClient):
    with patch("app.pipeline.tasks.scrape_and_run") as mock_task:
        mock_task.delay = MagicMock()
        create_resp = await logged_in_client.post("/datasources/google-play", json={
            "name": "To Delete",
            "app_id": "com.delete.me",
            "count": 10,
        })
    assert create_resp.status_code == 201
    ds_id = create_resp.json()["id"]

    del_resp = await logged_in_client.delete(f"/datasources/{ds_id}")
    assert del_resp.status_code == 204

    list_resp = await logged_in_client.get("/datasources")
    ids = [d["id"] for d in list_resp.json()]
    assert ds_id not in ids


async def test_delete_other_users_datasource_returns_404(client: AsyncClient, logged_in_client: AsyncClient):
    # Create a datasource as the logged-in user
    with patch("app.pipeline.tasks.scrape_and_run") as mock_task:
        mock_task.delay = MagicMock()
        create_resp = await logged_in_client.post("/datasources/google-play", json={
            "name": "Private App",
            "app_id": "com.private.app",
            "count": 10,
        })
    ds_id = create_resp.json()["id"]

    # A different (unauthenticated) user tries to delete it
    # Register + login as a second user
    await client.post("/auth/register", json={
        "email": "other_user@ma.com",
        "password": "Test1234!",
        "full_name": "Other",
    })
    await client.post("/auth/login", json={
        "email": "other_user@ma.com",
        "password": "Test1234!",
    })
    resp = await client.delete(f"/datasources/{ds_id}")
    assert resp.status_code == 404
