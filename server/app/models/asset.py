from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, condecimal

from app.models.common import Visibility, PortfolioKind

class AssetCreate(BaseModel):
    symbol: str = Field(min_length=2, max_length=16)  # BTC, ETH, SOL...
    display_name: Optional[str] = Field(default=None, max_length=32)
    emoji: Optional[str] = Field(default=None, max_length=8)

class AssetSummary(BaseModel):
    id: UUID
    symbol: str
    display_name: Optional[str]
    emoji: Optional[str]
