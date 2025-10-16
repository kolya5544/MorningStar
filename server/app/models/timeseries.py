from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, condecimal

from app.models.common import Visibility, PortfolioKind, TxType

class Timepoint(BaseModel):
    t: datetime
    balance_usd: condecimal(max_digits=18, decimal_places=2)

class TimeseriesResponse(BaseModel):
    points: List[Timepoint]
