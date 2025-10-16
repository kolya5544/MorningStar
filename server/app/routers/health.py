from fastapi import APIRouter
from datetime import datetime

router = APIRouter()
_started = datetime.utcnow()

@router.get("/")
def health():
    return {
        "status": "ok",
        "service": "morningstar-api",
        "time": datetime.utcnow().isoformat() + "Z",
        "uptimeSec": int((datetime.utcnow() - _started).total_seconds()),
        "version": "v0.1.0"
    }
