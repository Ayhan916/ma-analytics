#!/usr/bin/env python3
"""Run Alembic migrations with a PostgreSQL advisory lock.

Only one process at a time can hold the lock and run migrations.
Concurrent containers block until the first one finishes, then
see that the schema is already up to date and exit immediately.

Usage:
    python migrate.py
"""
from __future__ import annotations

import sys
import time
import psycopg2
from alembic.config import Config
from alembic import command

# Arbitrary lock ID — must be the same across all instances.
# Using the app's fixed numeric ID avoids lock namespace collisions.
_ADVISORY_LOCK_ID = 7_742_000_001


def _get_db_url() -> str:
    import os
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        from app.core.config import settings
        url = settings.DATABASE_URL
    # psycopg2 needs postgresql://, not asyncpg-style
    return url.replace("postgresql+asyncpg://", "postgresql://")


def run() -> None:
    db_url = _get_db_url()

    print("[migrate] Connecting to database...")
    conn = psycopg2.connect(db_url)
    conn.autocommit = True

    print(f"[migrate] Acquiring advisory lock {_ADVISORY_LOCK_ID}...")
    start = time.monotonic()
    cur = conn.cursor()

    # pg_advisory_lock blocks until the lock is available.
    # This is intentional: let the first container run migrations,
    # subsequent containers wait and then find nothing to do.
    cur.execute("SELECT pg_advisory_lock(%s)", (_ADVISORY_LOCK_ID,))
    elapsed = round(time.monotonic() - start, 2)
    print(f"[migrate] Lock acquired in {elapsed}s")

    try:
        print("[migrate] Running alembic upgrade head...")
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")
        print("[migrate] Migrations complete.")
    finally:
        cur.execute("SELECT pg_advisory_unlock(%s)", (_ADVISORY_LOCK_ID,))
        print("[migrate] Lock released.")
        cur.close()
        conn.close()


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"[migrate] FATAL: {exc}", file=sys.stderr)
        sys.exit(1)
