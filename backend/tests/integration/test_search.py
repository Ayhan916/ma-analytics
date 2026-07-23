"""Integration tests for /search endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_search_requires_auth(client: AsyncClient):
    resp = await client.get("/search?datasource_id=nonexistent&q=crash")
    assert resp.status_code == 401


async def test_search_nonexistent_datasource_returns_404(logged_in_client: AsyncClient):
    resp = await logged_in_client.get("/search?datasource_id=00000000-0000-0000-0000-000000000000&q=crash")
    assert resp.status_code == 404


async def test_search_missing_query_returns_422(logged_in_client: AsyncClient):
    resp = await logged_in_client.get("/search?datasource_id=some-id")
    assert resp.status_code == 422


async def test_search_query_too_short_returns_422(logged_in_client: AsyncClient):
    resp = await logged_in_client.get("/search?datasource_id=some-id&q=x")
    assert resp.status_code == 422


async def test_ask_requires_auth(client: AsyncClient):
    resp = await client.post("/search/ask", json={
        "query": "What are users saying?",
        "datasource_id": "00000000-0000-0000-0000-000000000000",
    })
    assert resp.status_code == 401


async def test_ask_nonexistent_datasource_returns_404(logged_in_client: AsyncClient):
    resp = await logged_in_client.post("/search/ask", json={
        "query": "What are users saying?",
        "datasource_id": "00000000-0000-0000-0000-000000000000",
    })
    assert resp.status_code == 404
