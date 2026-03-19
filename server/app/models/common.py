from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, HttpUrl, condecimal

class Visibility(str, Enum):
    public = "public"
    private = "private"

class PortfolioKind(str, Enum):
    personal = "personal"
    subscribed = "subscribed"

class Chain(str, Enum):
    eth = "ETH"
    sol = "SOL"

class TxType(str, Enum):
    buy = "buy"
    sell = "sell"
    transfer_in = "transfer_in"
    transfer_out = "transfer_out"

class Role(str, Enum):
    """User roles used for access control.

    - user: regular account owner who can create and manage their own data.
    - manager: may view all portfolios but cannot modify them.
    - admin: has full privileges including managing other users.
    """

    user = "user"
    manager = "manager"
    admin = "admin"

class ApiError(BaseModel):
    code: str
    message: str