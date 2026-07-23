#!/bin/sh
set -e
echo "[ma-analytics] Running database migrations..."
python migrate.py
echo "[ma-analytics] Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
