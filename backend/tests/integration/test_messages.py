"""Integration tests for /messages endpoints."""
from __future__ import annotations

import pytest
from unittest.mock import patch
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_list_messages_requires_auth(client: AsyncClient):
    resp = await client.get("/messages")
    assert resp.status_code == 401


async def test_list_messages_empty_initially(logged_in_client: AsyncClient):
    resp = await logged_in_client.get("/messages")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_create_message_returns_201(logged_in_client: AsyncClient):
    with patch("app.api.messages._detect_sentiment", return_value="positive"):
        resp = await logged_in_client.post("/messages", json={
            "name": "Max Mustermann",
            "email": "max@example.com",
            "text": "Great app, I love it!",
        })
    assert resp.status_code == 201
    body = resp.json()
    assert body["text"] == "Great app, I love it!"
    assert body["sentiment"] == "positive"
    assert "id" in body


async def test_create_message_negative_sentiment(logged_in_client: AsyncClient):
    with patch("app.api.messages._detect_sentiment", return_value="negative"):
        resp = await logged_in_client.post("/messages", json={
            "text": "This app is terrible, it keeps crashing.",
        })
    assert resp.status_code == 201
    assert resp.json()["sentiment"] == "negative"


async def test_filter_messages_by_sentiment(logged_in_client: AsyncClient):
    with patch("app.api.messages._detect_sentiment", return_value="positive"):
        await logged_in_client.post("/messages", json={"text": "Love this app!"})
    with patch("app.api.messages._detect_sentiment", return_value="negative"):
        await logged_in_client.post("/messages", json={"text": "Terrible experience."})

    pos_resp = await logged_in_client.get("/messages?sentiment=positive")
    assert pos_resp.status_code == 200
    for msg in pos_resp.json():
        assert msg["sentiment"] == "positive"

    neg_resp = await logged_in_client.get("/messages?sentiment=negative")
    assert neg_resp.status_code == 200
    for msg in neg_resp.json():
        assert msg["sentiment"] == "negative"


async def test_invalid_sentiment_filter_returns_400(logged_in_client: AsyncClient):
    resp = await logged_in_client.get("/messages?sentiment=unknown_value")
    assert resp.status_code == 400


async def test_create_message_without_name_or_email(logged_in_client: AsyncClient):
    with patch("app.api.messages._detect_sentiment", return_value="neutral"):
        resp = await logged_in_client.post("/messages", json={"text": "Just a message."})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] is None
    assert body["email"] is None
