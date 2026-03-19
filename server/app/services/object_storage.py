from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path


OBJECT_STORAGE_ROOT = Path(os.getenv("OBJECT_STORAGE_ROOT", "object_storage")).resolve()
OBJECT_STORAGE_SECRET = os.getenv("OBJECT_STORAGE_SECRET", os.getenv("JWT_SECRET", "dev-secret-change-me"))
MAX_FILE_SIZE_BYTES = int(os.getenv("OBJECT_STORAGE_MAX_FILE_SIZE", str(5 * 1024 * 1024)))
ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "application/pdf",
    "text/plain",
    "text/csv",
    "application/json",
}


class ObjectStorageError(Exception):
    pass


class ObjectStorageService:
    def __init__(self, root: Path | None = None):
        self.root = (root or OBJECT_STORAGE_ROOT).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def validate_upload(self, file_name: str, content_type: str, content_base64: str) -> bytes:
        if not file_name.strip():
            raise ObjectStorageError("File name is required")
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ObjectStorageError("Unsupported file type")
        try:
            payload = base64.b64decode(content_base64, validate=True)
        except Exception as exc:
            raise ObjectStorageError(f"Invalid file payload: {exc}")
        if len(payload) == 0:
            raise ObjectStorageError("Empty files are not allowed")
        if len(payload) > MAX_FILE_SIZE_BYTES:
            raise ObjectStorageError("File exceeds maximum allowed size")
        return payload

    def put_bytes(self, data: bytes, file_name: str) -> str:
        ext = Path(file_name).suffix[:16]
        storage_key = f"{secrets.token_hex(16)}{ext}"
        path = self.root / storage_key
        path.write_bytes(data)
        return storage_key

    def delete(self, storage_key: str) -> None:
        path = self.root / storage_key
        if path.exists():
            path.unlink()

    def read(self, storage_key: str) -> bytes:
        path = self.root / storage_key
        if not path.exists():
            raise ObjectStorageError("Stored file not found")
        return path.read_bytes()

    def build_presigned_token(self, file_id: str, expires_at: int) -> str:
        payload = f"{file_id}:{expires_at}"
        signature = hmac.new(
            OBJECT_STORAGE_SECRET.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{expires_at}.{signature}"

    def verify_presigned_token(self, file_id: str, token: str) -> None:
        try:
            expires_raw, signature = token.split(".", 1)
            expires_at = int(expires_raw)
        except Exception:
            raise ObjectStorageError("Invalid download token")
        if int(time.time()) >= expires_at:
            raise ObjectStorageError("Download token expired")
        expected = self.build_presigned_token(file_id, expires_at).split(".", 1)[1]
        if not hmac.compare_digest(signature, expected):
            raise ObjectStorageError("Invalid download token")
