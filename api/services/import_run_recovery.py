"""Startup recovery for orphan article_import_run rows.

When the backend dies mid-import (process kill, crash, OOM), the
in-flight generator can't run its finally clause, so the run row stays
RUNNING forever. On the next startup we sweep those and flip them to
FAILED so the UI surfaces them as resumable.
"""
from __future__ import annotations

from datetime import datetime


def mark_orphan_imports_failed() -> int:
    """Flip any RUNNING article_import_run rows to FAILED.

    Returns the number of rows updated. Safe to call on every startup;
    a no-op when there are no orphans.
    """
    from api.database import SessionLocal
    from api.models import ArticleImportRun

    db = SessionLocal()
    try:
        rows = db.query(ArticleImportRun).filter_by(status="RUNNING").all()
        if not rows:
            return 0
        now = datetime.utcnow()
        for row in rows:
            row.status = "FAILED"
            row.completed_at = now
            row.error_message = (
                "Import interrupted by server restart. "
                "Staged file retained; click Resume to continue."
            )
        db.commit()
        return len(rows)
    finally:
        db.close()
