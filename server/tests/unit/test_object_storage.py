from __future__ import annotations

import base64
import time

import pytest

from app.services.object_storage import ObjectStorageError, ObjectStorageService


@pytest.mark.unit
def test_validate_upload_rejects_empty_payload(tmp_path):
    service = ObjectStorageService(root=tmp_path)

    with pytest.raises(ObjectStorageError, match="Empty files are not allowed"):
        service.validate_upload("report.txt", "text/plain", base64.b64encode(b"").decode("ascii"))


@pytest.mark.unit
def test_put_read_and_verify_presigned_token(tmp_path):
    service = ObjectStorageService(root=tmp_path)
    payload = b"portfolio-data"

    key = service.put_bytes(payload, "report.txt")
    assert service.read(key) == payload

    token = service.build_presigned_token("file-1", int(time.time()) + 30)
    service.verify_presigned_token("file-1", token)

    with pytest.raises(ObjectStorageError, match="Invalid download token"):
        service.verify_presigned_token("file-2", token)
