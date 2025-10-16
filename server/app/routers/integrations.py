# app/routers/integrations.py
from uuid import uuid4, UUID
from fastapi import APIRouter
from app.models.integrations import WalletImportRequest, ImportJob, JobStatus, ExchangeConnectRequest

router = APIRouter()
_jobs: dict[UUID, ImportJob] = {}

@router.post("/import/wallet", response_model=ImportJob)
def import_wallet(req: WalletImportRequest):
    jid = uuid4()
    job = ImportJob(job_id=jid, status=JobStatus.queued)
    _jobs[jid] = job
    return job

@router.get("/import/wallet/{job_id}", response_model=ImportJob)
def job_status(job_id: UUID):
    return _jobs.get(job_id, ImportJob(job_id=job_id, status=JobStatus.error, message="not-found"))

@router.get("/integrations/exchanges")
def list_exchanges():
    return [{"id": "conn-demo", "exchange": "bybit", "label": "Bybit Demo", "connected": True}]

@router.post("/integrations/exchanges")
def connect_exchange(req: ExchangeConnectRequest):
    return {"id": "conn-" + str(uuid4())[:8], "exchange": req.exchange, "label": req.label, "connected": True}

@router.delete("/integrations/exchanges/{conn_id}", status_code=204)
def delete_exchange(conn_id: str):
    return
