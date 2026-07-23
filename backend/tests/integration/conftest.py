"""Integration test fixtures: test DB, app client, auth helpers."""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text
from httpx import AsyncClient, ASGITransport
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.conftest import TEST_DATABASE_URL
from app.main import app as fastapi_app
from app.core.database import get_db
from app.models.base import Base
# Import all models so Base.metadata is fully populated
import app.models.user          # noqa: F401
import app.models.datasource    # noqa: F401
import app.models.review        # noqa: F401
import app.models.cluster       # noqa: F401
import app.models.pipeline_job  # noqa: F401
import app.models.message       # noqa: F401
import app.models.ticket        # noqa: F401


# ---------------------------------------------------------------------------
# Session-scoped engine — tables created once, dropped after all tests
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    # NullPool: no connection reuse across asyncio tasks — required to avoid
    # asyncpg "another operation is in progress" with Starlette BaseHTTPMiddleware
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


_SESSION_FACTORY: async_sessionmaker | None = None


@pytest_asyncio.fixture(scope="session")
async def session_factory(test_engine):
    factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    return factory


# Tables that persist across tests — deleting them would trigger rate-limit
# re-registrations and slow things down unnecessarily
_PERSISTENT_TABLES = {"users"}


@pytest_asyncio.fixture(autouse=True)
async def _truncate_tables(test_engine):
    """Delete business data after each test; keep users to avoid rate-limit churn."""
    yield
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name not in _PERSISTENT_TABLES:
                await conn.execute(table.delete())


# ---------------------------------------------------------------------------
# Per-test client with dependency override
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(session_factory):
    """AsyncClient with get_db overridden to use the test DB."""
    async def _override_get_db():
        async with session_factory() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Disable slowapi rate limiting for tests
# Both the global limiter (app.state.limiter) and the per-module one in auth.py
# must be disabled so the test suite can make many requests without hitting limits.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def disable_rate_limits():
    from app.main import limiter as global_limiter
    import app.api.auth as auth_module

    global_limiter.enabled = False
    if hasattr(auth_module, "limiter"):
        auth_module.limiter.enabled = False
    yield
    global_limiter.enabled = True
    if hasattr(auth_module, "limiter"):
        auth_module.limiter.enabled = True


_TEST_USER = {
    "email": "test_integration@ma.com",
    "password": "Test1234!",
    "full_name": "Integration User",
}


@pytest_asyncio.fixture(scope="session")
async def _test_user_setup(session_factory):
    """Create the persistent test user directly in the DB — no HTTP, no rate limit."""
    import uuid
    from sqlalchemy import select
    from app.models.user import User
    from app.core.security import hash_password

    async with session_factory() as session:
        existing = (
            await session.execute(select(User).where(User.email == _TEST_USER["email"]))
        ).scalar_one_or_none()
        if not existing:
            user = User(
                id=str(uuid.uuid4()),
                email=_TEST_USER["email"],
                hashed_password=hash_password(_TEST_USER["password"]),
                full_name=_TEST_USER["full_name"],
            )
            session.add(user)
            await session.commit()


@pytest_asyncio.fixture
async def logged_in_client(client: AsyncClient, _test_user_setup) -> AsyncClient:
    """Login with the pre-created test user; cookies are set automatically."""
    resp = await client.post("/auth/login", json={
        "email": _TEST_USER["email"],
        "password": _TEST_USER["password"],
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return client
