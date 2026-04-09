import os
from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.db import engine

router = APIRouter()
_started = datetime.utcnow()

@router.get("/")
def health():
    db_status = "ok"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    return {
        "status": "ok",
        "service": os.getenv("SERVICE_NAME", "morningstar-api"),
        "time": datetime.utcnow().isoformat() + "Z",
        "uptimeSec": int((datetime.utcnow() - _started).total_seconds()),
        "version": os.getenv("SERVICE_VERSION", "v0.1.0"),
        "dependencies": {
            "database": db_status,
        },
    }
