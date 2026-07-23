"""Root conftest: shared fixtures for unit and integration tests."""
from __future__ import annotations

import os
import pytest


# Expose whether a test Postgres is reachable so integration tests can skip gracefully
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://ma_analytics:ma_analytics@localhost:5434/ma_analytics_test",
)

needs_postgres = pytest.mark.skipif(
    os.environ.get("SKIP_INTEGRATION", "0") == "1",
    reason="Integration tests skipped (SKIP_INTEGRATION=1)",
)
