#!/bin/sh
set -eu

python - <<'PY'
import os
import sys
import time

from sqlalchemy import text

from app.db import engine

retries = int(os.getenv("API_STARTUP_DB_RETRIES", "20"))
delay = float(os.getenv("API_STARTUP_DB_DELAY_SEC", "3"))

for attempt in range(1, retries + 1):
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("Database is ready")
        sys.exit(0)
    except Exception as exc:
        print(f"Database is not ready yet ({attempt}/{retries}): {exc}", flush=True)
        if attempt == retries:
            raise
        time.sleep(delay)
PY

exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers --forwarded-allow-ips='*'
