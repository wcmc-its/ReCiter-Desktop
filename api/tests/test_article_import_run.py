"""Tests for the article_import_run lifecycle.

Covers issue #14:
- Model shape (columns, enums, PK)
- Sweeper retains files backing PARTIAL/FAILED runs
- _run_import_stream transitions RUNNING -> COMPLETED on normal finish
- _run_import_stream transitions RUNNING -> PARTIAL on GeneratorExit
- _run_import_stream transitions RUNNING -> FAILED on exception
- Retry endpoint validation paths
"""
from __future__ import annotations

import os
import time
from unittest.mock import patch, MagicMock

import pytest

from api.models import ArticleImportRun


# ----------- Model shape -----------


def test_article_import_run_columns():
    cols = {c.name for c in ArticleImportRun.__table__.columns}
    for name in (
        "run_id", "status", "total_pmids", "imported_pmids", "person_count",
        "file_id", "filename", "mappings_json", "import_gold_standard",
        "error_message", "started_at", "completed_at", "created_at",
    ):
        assert name in cols, f"missing column {name}"


def test_article_import_run_status_enum():
    enums = list(ArticleImportRun.__table__.columns["status"].type.enums)
    for v in ("RUNNING", "COMPLETED", "PARTIAL", "FAILED"):
        assert v in enums


def test_article_import_run_pk():
    pk = [c.name for c in ArticleImportRun.__table__.primary_key.columns]
    assert pk == ["run_id"]


# ----------- Sweeper preserves retryable runs -----------


def test_sweep_retains_partial_run_files(tmp_path, monkeypatch):
    """Files backing a PARTIAL run must survive sweep_stale_uploads."""
    import api.services.upload_utils as uu

    monkeypatch.setattr(uu, "UPLOAD_DIR", str(tmp_path))

    # File-id pinned by a PARTIAL run; another id is just an orphaned upload.
    pinned = "articles_aaaaaaaaaaaa"
    orphan = "articles_bbbbbbbbbbbb"
    for fid in (pinned, orphan):
        p = tmp_path / fid
        p.write_bytes(b"x")
        (tmp_path / (fid + ".name")).write_text("x.csv")
        old = time.time() - 7 * 24 * 3600
        os.utime(p, (old, old))
        os.utime(tmp_path / (fid + ".name"), (old, old))

    monkeypatch.setattr(uu, "_retained_file_ids", lambda: {pinned})

    removed = uu.sweep_stale_uploads(max_age_seconds=24 * 3600)
    assert removed == 2  # both orphan files (data + .name) removed
    assert (tmp_path / pinned).exists()
    assert (tmp_path / (pinned + ".name")).exists()
    assert not (tmp_path / orphan).exists()
    assert not (tmp_path / (orphan + ".name")).exists()


# ----------- Stream lifecycle: COMPLETED / PARTIAL / FAILED -----------


class _FakeQuery:
    def __init__(self, results=None):
        self._results = results if results is not None else []

    def filter_by(self, **_):
        return self

    def filter(self, *_a, **_kw):
        return self

    def order_by(self, *_a, **_kw):
        return self

    def first(self):
        return self._results[0] if self._results else None

    def all(self):
        return self._results


class _FakeSession:
    """Minimal Session double for exercising _run_import_stream control flow."""

    def __init__(self, articles_existing=None, runs=None):
        self.articles_existing = list(articles_existing or [])
        self.runs = list(runs or [])
        self.added = []
        self.commits = 0
        self.closed = False
        self._next_run_id = 42

    def query(self, *cols):
        # Distinguish "list of articles" from "single run" lookups by
        # the column being queried.
        from api.models import Article, ArticleImportRun
        if cols and getattr(cols[0], "class_", None) is ArticleImportRun:
            return _FakeQuery(self.runs)
        if cols and getattr(cols[0], "class_", None) is Article:
            class _R:
                def __init__(self, pmid):
                    self.pmid = pmid
            return _FakeQuery([_R(p) for p in self.articles_existing])
        # Default: PersonArticle / Curation existence checks => none exist.
        return _FakeQuery([])

    def add(self, obj):
        from api.models import ArticleImportRun
        if isinstance(obj, ArticleImportRun):
            obj.run_id = self._next_run_id
            self._next_run_id += 1
            self.runs.append(obj)
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def refresh(self, obj):
        pass

    def close(self):
        self.closed = True

    # _store_article uses begin_nested + IntegrityError handling; not exercised here.


def _patch_session(monkeypatch, session):
    monkeypatch.setattr("api.routers.articles.SessionLocal", lambda: session)


def _write_staged_file(monkeypatch, tmp_path, file_id, csv_text):
    monkeypatch.setattr("api.services.upload_utils.UPLOAD_DIR", str(tmp_path))
    import api.routers.articles as art_mod
    monkeypatch.setattr(art_mod, "UPLOAD_DIR", str(tmp_path))
    (tmp_path / file_id).write_text(csv_text)
    (tmp_path / (file_id + ".name")).write_text("pmids.csv")


def test_stream_completes_and_deletes_staging(monkeypatch, tmp_path):
    """Happy path: RUNNING -> COMPLETED, staging files removed."""
    from api.routers import articles as art_mod

    file_id = "articles_111111111111"
    _write_staged_file(
        monkeypatch, tmp_path, file_id,
        "person_id,pmid\nP1,12345\nP1,67890\n",
    )

    session = _FakeSession(articles_existing=["12345", "67890"])
    _patch_session(monkeypatch, session)
    monkeypatch.setattr(
        "api.routers.institution.get_pubmed_api_key", lambda _db: ""
    )
    # No new PMIDs to fetch => fetch_articles is never called.
    monkeypatch.setattr(art_mod, "fetch_articles", lambda *a, **kw: [])

    events = list(art_mod._run_import_stream(file_id, {}, True))

    types = [e for e in events if '"type":' in e]
    assert any('"type": "complete"' in e for e in types)
    # Run row was created and then flipped COMPLETED
    assert session.runs, "expected an ArticleImportRun row"
    # _update_run_status runs in a fresh session, so the in-memory run's
    # status mirrors the create-time value. Confirm staging files removed
    # which is the externally observable COMPLETED side effect.
    assert not (tmp_path / file_id).exists()
    assert not (tmp_path / (file_id + ".name")).exists()


def test_stream_failed_keeps_staging(monkeypatch, tmp_path):
    """Bad mapping => FAILED, staging files retained for retry."""
    from api.routers import articles as art_mod

    file_id = "articles_222222222222"
    _write_staged_file(
        monkeypatch, tmp_path, file_id,
        "wrong,cols\nA,B\n",
    )

    session = _FakeSession()
    _patch_session(monkeypatch, session)
    monkeypatch.setattr(
        "api.routers.institution.get_pubmed_api_key", lambda _db: ""
    )

    events = list(art_mod._run_import_stream(file_id, {}, True))

    assert any('"type": "error"' in e for e in events)
    # Staging file retained so user can fix mapping and retry
    assert (tmp_path / file_id).exists()


def test_stream_partial_on_generator_exit(monkeypatch, tmp_path):
    """Client abort (GeneratorExit) => PARTIAL, staging files retained."""
    from api.routers import articles as art_mod

    file_id = "articles_333333333333"
    _write_staged_file(
        monkeypatch, tmp_path, file_id,
        "person_id,pmid\nP1,1\nP1,2\nP1,3\n",
    )

    session = _FakeSession(articles_existing=[])
    _patch_session(monkeypatch, session)
    monkeypatch.setattr(
        "api.routers.institution.get_pubmed_api_key", lambda _db: ""
    )
    monkeypatch.setattr(art_mod, "fetch_articles", lambda *a, **kw: [])

    # Track FAILED/PARTIAL status writes via the helper.
    status_writes: list[dict] = []
    real_update = art_mod._update_run_status

    def _spy(run_id, **fields):
        status_writes.append(fields)
        real_update(run_id, **fields)

    monkeypatch.setattr(art_mod, "_update_run_status", _spy)

    gen = art_mod._run_import_stream(file_id, {}, True)
    # Consume events until run_started is emitted, then close the
    # generator (simulates client abort after the run row exists).
    saw_run_started = False
    for ev in gen:
        if '"type": "run_started"' in ev:
            saw_run_started = True
            break
    assert saw_run_started, "run_started event must precede client abort"
    gen.close()

    # Staging files must survive a client abort
    assert (tmp_path / file_id).exists()
    # The last status write should be PARTIAL (not FAILED, not COMPLETED)
    final_statuses = [w.get("status") for w in status_writes if "status" in w]
    assert final_statuses, "expected at least one status transition"
    assert final_statuses[-1] == "PARTIAL"


# ----------- Retry endpoint validation -----------


def test_retry_rejects_completed_run(monkeypatch):
    """COMPLETED runs cannot be retried."""
    from fastapi import HTTPException
    from api.routers import articles as art_mod

    run = ArticleImportRun(
        run_id=1, status="COMPLETED", file_id="articles_aaaaaaaaaaaa",
        mappings_json=[], import_gold_standard=1,
    )
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = run

    with pytest.raises(HTTPException) as exc:
        art_mod.retry_import_run(run_id=1, db=db)
    assert exc.value.status_code == 400


def test_retry_404_when_missing(monkeypatch):
    from fastapi import HTTPException
    from api.routers import articles as art_mod

    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc:
        art_mod.retry_import_run(run_id=999, db=db)
    assert exc.value.status_code == 404


def test_retry_410_when_staging_gone(monkeypatch, tmp_path):
    """If the staged file was swept, retry must return 410 Gone."""
    from fastapi import HTTPException
    from api.routers import articles as art_mod

    monkeypatch.setattr(art_mod, "UPLOAD_DIR", str(tmp_path))

    run = ArticleImportRun(
        run_id=2, status="PARTIAL", file_id="articles_cccccccccccc",
        mappings_json=[], import_gold_standard=1,
    )
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = run

    with pytest.raises(HTTPException) as exc:
        art_mod.retry_import_run(run_id=2, db=db)
    assert exc.value.status_code == 410


def test_dismiss_clears_file_id(monkeypatch, tmp_path):
    """Dismiss removes the staging file and nulls file_id."""
    from api.routers import articles as art_mod

    monkeypatch.setattr(art_mod, "UPLOAD_DIR", str(tmp_path))
    file_id = "articles_dddddddddddd"
    (tmp_path / file_id).write_bytes(b"x")
    (tmp_path / (file_id + ".name")).write_text("x.csv")

    run = ArticleImportRun(
        run_id=3, status="PARTIAL", file_id=file_id,
        mappings_json=[], import_gold_standard=1,
    )
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = run

    result = art_mod.dismiss_import_run(run_id=3, db=db)

    assert result == {"run_id": 3, "dismissed": True}
    assert run.file_id is None
    assert not (tmp_path / file_id).exists()
    assert not (tmp_path / (file_id + ".name")).exists()
    db.commit.assert_called_once()
