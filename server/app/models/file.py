from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PortfolioFileUploadRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=120)
    content_base64: str = Field(min_length=4)


class PortfolioFileItem(BaseModel):
    id: UUID
    portfolio_id: UUID
    uploaded_by_user_id: UUID
    original_name: str
    content_type: str
    size_bytes: int
    created_at: datetime


class PortfolioFileDownloadResponse(BaseModel):
    download_url: str
    expires_at: int
