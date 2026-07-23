"""Integration tests for /auth endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


_USER = {
    "email": "auth_test_user@ma.com",
    "password": "Test1234!",
    "full_name": "Auth Test User",
}


async def test_register_creates_user(client: AsyncClient):
    resp = await client.post("/auth/register", json=_USER)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == _USER["email"]
    assert "id" in body


async def test_register_duplicate_returns_400(client: AsyncClient):
    await client.post("/auth/register", json=_USER)
    resp = await client.post("/auth/register", json=_USER)
    assert resp.status_code == 400


async def test_register_weak_password_returns_400(client: AsyncClient):
    resp = await client.post("/auth/register", json={**_USER, "email": "weak@ma.com", "password": "short"})
    assert resp.status_code == 400


async def test_login_returns_200_and_sets_cookie(client: AsyncClient):
    await client.post("/auth/register", json=_USER)
    resp = await client.post("/auth/login", json={
        "email": _USER["email"],
        "password": _USER["password"],
    })
    assert resp.status_code == 200
    assert "access_token" in resp.cookies


async def test_login_wrong_password_returns_401(client: AsyncClient):
    await client.post("/auth/register", json=_USER)
    resp = await client.post("/auth/login", json={
        "email": _USER["email"],
        "password": "WrongPassword!",
    })
    assert resp.status_code == 401


async def test_me_returns_user_when_authenticated(logged_in_client: AsyncClient):
    resp = await logged_in_client.get("/auth/me")
    assert resp.status_code == 200
    assert "email" in resp.json()


async def test_me_returns_401_when_not_authenticated(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_logout_clears_cookie(logged_in_client: AsyncClient):
    resp = await logged_in_client.post("/auth/logout")
    assert resp.status_code in (200, 204)
