from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, condecimal

from app.models.common import Visibility, PortfolioKind


class PortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    emoji: Optional[str] = Field(default=None, max_length=8)  # до 3 эмодзи ок
    visibility: Visibility = Visibility.private

class PortfolioSummary(BaseModel):
    id: UUID
    name: str
    emoji: Optional[str]
    balance_usd: condecimal(max_digits=18, decimal_places=2)
    pnl_day_usd: condecimal(max_digits=18, decimal_places=2)
    kind: PortfolioKind = PortfolioKind.personal
    visibility: Optional[Visibility]  # только для personal

class PortfolioDetail(PortfolioSummary):
    created_at: datetime
