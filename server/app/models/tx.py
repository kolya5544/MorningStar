from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, condecimal

from app.models.common import Visibility, PortfolioKind, TxType


class TxCreate(BaseModel):
    asset_id: UUID
    type: TxType
    quantity: condecimal(max_digits=28, decimal_places=8)
    price_usd: Optional[condecimal(max_digits=18, decimal_places=2)] = None
    fee_usd: Optional[condecimal(max_digits=18, decimal_places=2)] = None
    at: datetime
    note: Optional[str] = Field(default=None, max_length=140)
    tx_hash: Optional[str] = Field(default=None, max_length=128)

class TxItem(TxCreate):
    id: UUID
