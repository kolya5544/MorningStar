from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.orm_models import PortfolioFileORM
from app.services.object_storage import ObjectStorageError, ObjectStorageService

router = APIRouter()


@router.get("/public/portfolios/{pid}/files/{file_id}/content")
def download_portfolio_file_content(
    pid: UUID,
    file_id: UUID,
    token: str = Query(..., min_length=10),
    db: Session = Depends(get_db),
):
    file_meta = db.get(PortfolioFileORM, str(file_id))
    if not file_meta or file_meta.portfolio_id != str(pid):
        raise HTTPException(status_code=404, detail="File not found")

    storage = ObjectStorageService()
    try:
        storage.verify_presigned_token(file_meta.id, token)
        payload = storage.read(file_meta.storage_key)
    except ObjectStorageError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    headers = {
        "Content-Disposition": f'attachment; filename="{file_meta.original_name}"',
    }
    return Response(content=payload, media_type=file_meta.content_type, headers=headers)
