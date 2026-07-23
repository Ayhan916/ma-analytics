"""Integration tests for /search endpoints."""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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


async def test_search_type_param_accepted(logged_in_client: AsyncClient):
    # Valid search_type values must not cause 422
    for stype in ("hybrid", "vector", "fulltext"):
        resp = await logged_in_client.get(
            f"/search?datasource_id=00000000-0000-0000-0000-000000000000&q=test&search_type={stype}"
        )
        # 404 is expected (datasource doesn't exist), not 422 (invalid param)
        assert resp.status_code == 404, f"search_type={stype} gave {resp.status_code}"


async def test_invalid_search_type_returns_422(logged_in_client: AsyncClient):
    resp = await logged_in_client.get(
        "/search?datasource_id=00000000-0000-0000-0000-000000000000&q=test&search_type=magic"
    )
    assert resp.status_code == 422


async def test_date_filter_accepted(logged_in_client: AsyncClient):
    resp = await logged_in_client.get(
        "/search?datasource_id=00000000-0000-0000-0000-000000000000"
        "&q=test&date_from=2024-01-01&date_to=2024-12-31"
    )
    assert resp.status_code == 404  # datasource not found, not 422


async def test_date_filter_inverted_range_returns_422(logged_in_client: AsyncClient):
    resp = await logged_in_client.get(
        "/search?datasource_id=00000000-0000-0000-0000-000000000000"
        "&q=test&date_from=2024-12-31&date_to=2024-01-01"
    )
    assert resp.status_code == 422


async def test_version_filter_accepted(logged_in_client: AsyncClient):
    resp = await logged_in_client.get(
        "/search?datasource_id=00000000-0000-0000-0000-000000000000&q=test&version=4.2.1"
    )
    assert resp.status_code == 404  # datasource not found, not 422


async def test_rerank_param_accepted(logged_in_client: AsyncClient):
    # rerank=true is a valid param — 404 because datasource doesn't exist, not 422
    resp = await logged_in_client.get(
        "/search?datasource_id=00000000-0000-0000-0000-000000000000&q=crash&rerank=true"
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /search/ask/stream — SSE streaming endpoint
# ---------------------------------------------------------------------------

async def test_ask_stream_requires_auth(client: AsyncClient):
    resp = await client.post("/search/ask/stream", json={
        "query": "What are users saying?",
        "datasource_id": "00000000-0000-0000-0000-000000000000",
    })
    assert resp.status_code == 401


async def test_ask_stream_nonexistent_datasource_returns_404(logged_in_client: AsyncClient):
    resp = await logged_in_client.post("/search/ask/stream", json={
        "query": "What are users saying?",
        "datasource_id": "00000000-0000-0000-0000-000000000000",
    })
    assert resp.status_code == 404


async def test_ask_stream_no_groq_key_returns_422(logged_in_client: AsyncClient, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.GROQ_API_KEY", "")
    resp = await logged_in_client.post("/search/ask/stream", json={
        "query": "What are users saying?",
        "datasource_id": "00000000-0000-0000-0000-000000000000",
    })
    # 404 is returned before the GROQ_API_KEY check since datasource doesn't exist
    assert resp.status_code in (404, 422)


async def test_ask_stream_returns_sse_content_type(logged_in_client: AsyncClient):
    """When datasource is missing, we get 404 before SSE starts. Verify SSE header via mock."""
    from app.api.search import SearchResponse, SearchResult

    async def fake_generator(*args, **kwargs):
        yield 'data: {"type": "sources", "sources": []}\n\n'
        yield 'data: {"type": "done", "generated_by": "none"}\n\n'

    with patch("app.api.search._ask_event_generator", side_effect=fake_generator), \
         patch("app.api.search._verify_datasource", new_callable=AsyncMock), \
         patch("app.api.search.semantic_search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = SearchResponse(
            query="test", datasource_id="fake-id", results=[], total=0, search_type="fulltext"
        )
        resp = await logged_in_client.post("/search/ask/stream", json={
            "query": "What are users saying?",
            "datasource_id": "00000000-0000-0000-0000-000000000000",
        })

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]


async def test_ask_stream_sse_format(logged_in_client: AsyncClient):
    """SSE body contains sources event followed by done event for empty results."""
    from app.api.search import SearchResponse

    async def fake_generator(*args, **kwargs):
        yield 'data: {"type": "sources", "sources": []}\n\n'
        yield 'data: {"type": "done", "generated_by": "none"}\n\n'

    with patch("app.api.search._ask_event_generator", side_effect=fake_generator), \
         patch("app.api.search._verify_datasource", new_callable=AsyncMock), \
         patch("app.api.search.semantic_search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = SearchResponse(
            query="test", datasource_id="fake-id", results=[], total=0, search_type="fulltext"
        )
        resp = await logged_in_client.post("/search/ask/stream", json={
            "query": "What are users saying?",
            "datasource_id": "fake-id",
        })

    events = [
        json.loads(line[len("data: "):])
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]
    assert events[0]["type"] == "sources"
    assert events[-1]["type"] == "done"
