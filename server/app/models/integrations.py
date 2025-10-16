from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, condecimal

from app.models.common import Visibility, PortfolioKind, TxType, Chain


class WalletImportRequest(BaseModel):
    chain: Chain
    address: str = Field(min_length=16, max_length=128)

class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    error = "error"

class ImportJob(BaseModel):
    job_id: UUID
    status: JobStatus
    message: Optional[str] = None

class Exchange(str, Enum):
    bybit = "bybit"

class ExchangeConnectRequest(BaseModel):
    exchange: Exchange
    label: Optional[str] = Field(default="Bybit")
    api_key: str
    api_secret: str  # хранение — потом, для ЛР5/6
