"""Shared helpers for staged file uploads.

Two upload flows (researchers, articles) write files into `api/_uploads/`
and reference them later by `file_id`. These helpers centralize the
validation and size-capping that both flows need:

- `validate_file_id` rejects file_id values that don't match the
  expected `<prefix>_<12 hex chars>` shape, preventing path traversal
  via concatenation into UPLOAD_DIR.
- `save_upload_streaming` streams an UploadFile to disk with a hard
  size cap so a malicious client cannot exhaust memory or disk.
- `sweep_stale_uploads` removes upload files older than a configurable
  age, intended to run on app startup.
"""

from __future__ import annotations

import os
import re
import time
from fastapi import HTTPException, UploadFile

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

_FILE_ID_RE = re.compile(r"^(upload|articles)_[0-9a-f]{12}$")

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
STALE_UPLOAD_SECONDS = 24 * 60 * 60   # 24 hours


def validate_file_id(file_id: str) -> None:
    """Raise 400 if `file_id` is not a safe upload identifier."""
    if not _FILE_ID_RE.match(file_id or ""):
        raise HTTPException(status_code=400, detail="Invalid file_id")


def upload_path(file_id: str) -> str:
    """Return the absolute staging path for a validated file_id."""
    validate_file_id(file_id)
    return os.path.join(UPLOAD_DIR, file_id)


async def save_upload_streaming(file: UploadFile, filepath: str) -> bytes:
    """Stream `file` to `filepath`, enforcing MAX_UPLOAD_BYTES.

    Returns the bytes written so callers can re-parse without re-reading
    from disk. Removes the partial file and raises 413 if the cap is
    exceeded.
    """
    size = 0
    chunks: list[bytes] = []
    with open(filepath, "wb") as out:
        while True:
            chunk = await file.read(1 << 20)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                try:
                    os.remove(filepath)
                except OSError:
                    pass
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
                )
            out.write(chunk)
            chunks.append(chunk)
    return b"".join(chunks)


def sweep_stale_uploads(max_age_seconds: int = STALE_UPLOAD_SECONDS) -> int:
    """Delete files in UPLOAD_DIR older than `max_age_seconds`.

    Returns the number of files removed. Intended to be called on app
    startup to bound disk growth from abandoned uploads.
    """
    if not os.path.isdir(UPLOAD_DIR):
        return 0
    cutoff = time.time() - max_age_seconds
    removed = 0
    for name in os.listdir(UPLOAD_DIR):
        path = os.path.join(UPLOAD_DIR, name)
        try:
            if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed += 1
        except OSError:
            continue
    return removed
