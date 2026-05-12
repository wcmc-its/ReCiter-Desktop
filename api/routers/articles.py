import io
import json
import logging
import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import pandas as pd

from api.database import SessionLocal, get_db
from api.models import Article, ArticleImportRun, PersonArticle, Curation
from api.services.column_mapper import detect_mappings
from api.services.upload_utils import (
    UPLOAD_DIR,
    save_upload_streaming,
    upload_path,
    validate_file_id,
)
from core.pubmed import fetch_articles

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/articles", tags=["articles"])


class ColumnMapping(BaseModel):
    original: str
    canonical: str | None


class ImportRequest(BaseModel):
    file_id: str
    mappings: list[ColumnMapping]
    import_gold_standard: bool = True


def _read_dataframe(content: bytes, filename: str) -> pd.DataFrame:
    if filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(content))
    if filename.endswith(".tsv"):
        return pd.read_csv(io.BytesIO(content), sep="\t")
    try:
        df = pd.read_csv(io.BytesIO(content))
        if len(df.columns) <= 1:
            df = pd.read_csv(io.BytesIO(content), sep="\t")
        return df
    except Exception:
        return pd.read_excel(io.BytesIO(content))


def _store_article(db: Session, art) -> bool:
    """Insert an article. Returns True if newly stored, False if it
    already exists.

    Uses a savepoint so a race with a concurrent import (both checked
    "not exists" then both INSERTed the same pmid) raises IntegrityError
    on the inner write only, not the whole chunk transaction. The losing
    side just reports "not new" and moves on.
    """
    pmid_str = str(art.pmid)
    if db.query(Article).filter_by(pmid=pmid_str).first():
        return False
    try:
        with db.begin_nested():
            db.add(Article(
                pmid=pmid_str,
                title=art.title,
                journal=art.journal_title,
                pub_year=art.pub_year,
                doi=art.doi,
                abstract_text=art.abstract,
                authors=[{
                    "first_name": a.first_name, "last_name": a.last_name,
                    "initials": a.initials, "affiliation": a.affiliation,
                    "orcid": getattr(a, "orcid", ""),
                } for a in art.authors],
                mesh_headings=[{
                    "descriptor_name": m.descriptor_name,
                    "major_topic": m.major_topic,
                } for m in art.mesh_headings] if art.mesh_headings else [],
                keywords=art.keywords or [],
                grants=art.grants or [],
                publication_types=art.publication_types or [],
            ))
        return True
    except IntegrityError:
        # Lost the insert race to another concurrent importer; the
        # article is now in the DB, just not from us.
        return False


def _run_dict(run: ArticleImportRun) -> dict:
    return {
        "run_id": run.run_id,
        "status": run.status,
        "total_pmids": run.total_pmids,
        "imported_pmids": run.imported_pmids,
        "person_count": run.person_count,
        "file_id": run.file_id,
        "filename": run.filename,
        "import_gold_standard": bool(run.import_gold_standard),
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def _update_run_status(run_id: int, **fields) -> None:
    """Update a run row in its own short-lived session.

    Used from the streaming generator's finally clause so the lifecycle
    transition survives a closed/aborted main session.
    """
    db = SessionLocal()
    try:
        run = db.query(ArticleImportRun).filter_by(run_id=run_id).first()
        if not run:
            return
        for k, v in fields.items():
            setattr(run, k, v)
        db.commit()
    finally:
        db.close()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Stage a file: parse headers, detect column mappings, return a preview.

    No DB writes happen here. Caller must follow up with POST /import.
    """
    filename = file.filename or "pmids.csv"

    file_id = f"articles_{uuid.uuid4().hex[:12]}"
    filepath = upload_path(file_id)
    content = await save_upload_streaming(file, filepath)
    # Persist original filename so /import can pick the right reader
    with open(filepath + ".name", "w") as f:
        f.write(filename)

    try:
        df = _read_dataframe(content, filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {e}")

    headers = list(df.columns)
    mappings = detect_mappings(headers)
    preview_rows = df.head(3).fillna("").to_dict(orient="records")

    has_assertion = any(mappings.get(h) == "assertion" for h in headers)
    assertion_count = 0
    if has_assertion:
        assertion_col = next(h for h in headers if mappings.get(h) == "assertion")
        assertion_count = int(df[assertion_col].notna().sum())

    return {
        "file_id": file_id,
        "filename": filename,
        "row_count": int(len(df)),
        "mappings": [
            {
                "original": h,
                "canonical": mappings.get(h),
                "sample": str(preview_rows[0].get(h, "")) if preview_rows else "",
            }
            for h in headers
        ],
        "preview": preview_rows,
        "has_gold_standard": has_assertion,
        "gold_standard_count": assertion_count,
    }


def _run_import_stream(
    file_id: str,
    rename_map: dict,
    import_gold_standard: bool,
    existing_run_id: int | None = None,
):
    """Generator producing SSE events for an article import.

    On entry, either reuses an existing RUNNING run row (retry) or creates
    a new one. Transitions:
      RUNNING -> COMPLETED on normal finish (staging file deleted)
      RUNNING -> FAILED    on uncaught exception (staging file kept)
      RUNNING -> PARTIAL   on client disconnect (staging file kept)
    """
    filepath = upload_path(file_id)
    name_path = filepath + ".name"
    filename = "pmids.csv"
    if os.path.exists(name_path):
        with open(name_path) as f:
            filename = f.read().strip() or filename

    db = SessionLocal()
    run_id: int | None = existing_run_id
    finished_cleanly = False
    failure_message: str | None = None
    try:
        try:
            with open(filepath, "rb") as f:
                content = f.read()

            yield f"data: {json.dumps({'type': 'status', 'message': 'Reading file...'})}\n\n"

            try:
                df = _read_dataframe(content, filename)
            except Exception as e:
                failure_message = f"Could not parse file: {e}"
                yield f"data: {json.dumps({'type': 'error', 'message': failure_message})}\n\n"
                return

            df = df.rename(columns=rename_map)

            if "person_id" not in df.columns or "pmid" not in df.columns:
                failure_message = "File must map both person_id and pmid columns."
                yield f"data: {json.dumps({'type': 'error', 'message': failure_message})}\n\n"
                return

            from api.routers.institution import get_pubmed_api_key
            api_key = get_pubmed_api_key(db)

            df = df.dropna(subset=["pmid"])
            try:
                all_pmids = [int(p) for p in df["pmid"].astype(int).unique()]
            except (ValueError, TypeError) as e:
                failure_message = f"Invalid PMID value: {e}"
                yield f"data: {json.dumps({'type': 'error', 'message': failure_message})}\n\n"
                return

            person_count = df["person_id"].dropna().nunique()
            has_assertions = import_gold_standard and "assertion" in df.columns

            existing_pmids = {str(a.pmid) for a in db.query(Article.pmid).all()}
            new_pmids = [p for p in all_pmids if str(p) not in existing_pmids]
            already_existed = len(all_pmids) - len(new_pmids)

            # Create or refresh the run row now that we know the totals.
            mappings_json = [
                {"original": k, "canonical": v} for k, v in rename_map.items()
            ]
            if run_id is None:
                run = ArticleImportRun(
                    status="RUNNING",
                    total_pmids=len(all_pmids),
                    imported_pmids=already_existed,
                    person_count=int(person_count),
                    file_id=file_id,
                    filename=filename,
                    mappings_json=mappings_json,
                    import_gold_standard=1 if import_gold_standard else 0,
                    started_at=datetime.utcnow(),
                )
                db.add(run)
                db.commit()
                db.refresh(run)
                run_id = run.run_id
            else:
                run = db.query(ArticleImportRun).filter_by(run_id=run_id).first()
                if run:
                    run.status = "RUNNING"
                    run.total_pmids = len(all_pmids)
                    run.imported_pmids = already_existed
                    run.person_count = int(person_count)
                    run.error_message = None
                    run.started_at = datetime.utcnow()
                    run.completed_at = None
                    db.commit()

            yield f"data: {json.dumps({'type': 'run_started', 'run_id': run_id, 'total_pmids': len(all_pmids), 'already_imported': already_existed})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'message': f'{len(all_pmids)} unique PMIDs ({already_existed} already on file, {len(new_pmids)} to fetch)'})}\n\n"

            # Collect per-batch progress events from the synchronous fetcher.
            progress_events: list[dict] = []

            def on_batch(event: dict):
                progress_events.append(event)

            article_count = 0
            imported_total = already_existed
            if new_pmids:
                yield f"data: {json.dumps({'type': 'status', 'message': 'Fetching metadata from PubMed...'})}\n\n"
                CHUNK = 200
                chunks = [new_pmids[i:i + CHUNK] for i in range(0, len(new_pmids), CHUNK)]
                requested_total = 0
                for chunk_idx, chunk in enumerate(chunks, start=1):
                    progress_events.clear()
                    fetched = fetch_articles(chunk, api_key=api_key or "", on_batch=on_batch)
                    chunk_new = 0
                    for art in fetched:
                        if _store_article(db, art):
                            article_count += 1
                            chunk_new += 1
                    db.commit()
                    requested_total += len(chunk)
                    imported_total += chunk_new
                    # Persist progress so a client abort after this commit
                    # leaves an accurate imported_pmids count.
                    _update_run_status(run_id, imported_pmids=imported_total)
                    for ev in progress_events:
                        merged = {
                            "type": "fetch_progress",
                            "batch": chunk_idx,
                            "batches": len(chunks),
                            "fetched": requested_total,
                            "total": len(new_pmids),
                        }
                        if "error" in ev:
                            merged["error"] = ev["error"]
                        yield f"data: {json.dumps(merged)}\n\n"

            known_pmids = {str(a.pmid) for a in db.query(Article.pmid).all()}

            yield f"data: {json.dumps({'type': 'status', 'message': 'Linking researchers to articles...'})}\n\n"
            link_count = 0
            for _, row in df.iterrows():
                pid = str(row["person_id"]).strip()
                try:
                    pmid = str(int(row["pmid"])).strip()
                except (ValueError, TypeError):
                    continue
                if pid and pmid and pmid in known_pmids:
                    existing = db.query(PersonArticle).filter_by(
                        person_id=pid, pmid=pmid
                    ).first()
                    if not existing:
                        db.add(PersonArticle(person_id=pid, pmid=pmid, source="upload"))
                        link_count += 1

            curation_count = 0
            if has_assertions:
                yield f"data: {json.dumps({'type': 'status', 'message': 'Importing assertions...'})}\n\n"
                for _, row in df.iterrows():
                    pid = str(row["person_id"]).strip()
                    try:
                        pmid = str(int(row["pmid"])).strip()
                    except (ValueError, TypeError):
                        continue
                    assertion = str(row.get("assertion", "")).strip().upper()
                    if pid and pmid and pmid in known_pmids and assertion in ("ACCEPTED", "REJECTED"):
                        existing = db.query(Curation).filter_by(
                            person_id=pid, pmid=pmid
                        ).first()
                        if not existing:
                            db.add(Curation(
                                person_id=pid, pmid=pmid,
                                assertion=assertion, source="import",
                            ))
                            curation_count += 1

            db.commit()

            yield f"data: {json.dumps({'type': 'complete', 'run_id': run_id, 'articles_fetched': article_count, 'links_created': link_count, 'curations_imported': curation_count, 'total_pmids': len(all_pmids), 'already_existed': already_existed})}\n\n"
            finished_cleanly = True
        except GeneratorExit:
            # Client disconnected mid-stream. Mark PARTIAL and re-raise so
            # FastAPI completes the response cleanup.
            raise
        except Exception as exc:
            logger.exception("Article import failed")
            failure_message = f"Import failed: {exc}"
            try:
                db.rollback()
            except Exception:
                pass
            try:
                yield f"data: {json.dumps({'type': 'error', 'message': failure_message})}\n\n"
            except Exception:
                pass
    finally:
        # Lifecycle transition. Use a fresh session because `db` may be
        # in an unusable state after an exception or client abort.
        if run_id is not None:
            if finished_cleanly:
                _update_run_status(
                    run_id,
                    status="COMPLETED",
                    completed_at=datetime.utcnow(),
                    error_message=None,
                )
                # On success, delete staging files (no retry needed).
                for p in (filepath, name_path):
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except OSError:
                            pass
            elif failure_message is not None:
                _update_run_status(
                    run_id,
                    status="FAILED",
                    completed_at=datetime.utcnow(),
                    error_message=failure_message,
                )
            else:
                # No `complete` event, no exception => client disconnect.
                _update_run_status(
                    run_id,
                    status="PARTIAL",
                    completed_at=datetime.utcnow(),
                )
        try:
            db.close()
        except Exception:
            pass


@router.post("/import")
def import_articles(req: ImportRequest):
    """Import staged PMIDs with SSE progress events.

    Stream events (newline-delimited `data: {json}\\n\\n`):
      - {type: "status", message}
      - {type: "run_started", run_id, total_pmids, already_imported}
      - {type: "fetch_progress", batch, batches, fetched, total, error?}
      - {type: "complete", run_id, articles_fetched, links_created,
                            curations_imported, total_pmids, already_existed}
      - {type: "error", message}
    """
    filepath = upload_path(req.file_id)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Upload not found. Please re-upload the file.")

    rename_map = {m.original: m.canonical for m in req.mappings if m.canonical}
    return StreamingResponse(
        _run_import_stream(req.file_id, rename_map, req.import_gold_standard),
        media_type="text/event-stream",
    )


@router.get("/import-runs/latest")
def latest_import_run(db: Session = Depends(get_db)):
    """Return the most recent import run, or null if none exist.

    The articles page polls this to surface partial-state banners.
    """
    run = (
        db.query(ArticleImportRun)
        .order_by(ArticleImportRun.run_id.desc())
        .first()
    )
    if not run:
        return None
    body = _run_dict(run)
    # Tell the client whether retry is actually viable (staging file
    # may have been swept by sweep_stale_uploads after 24h).
    body["retry_available"] = (
        run.status in ("PARTIAL", "FAILED")
        and run.file_id is not None
        and os.path.exists(os.path.join(UPLOAD_DIR, run.file_id))
    )
    return body


@router.post("/import-runs/{run_id}/retry")
def retry_import_run(run_id: int, db: Session = Depends(get_db)):
    """Resume a PARTIAL or FAILED import.

    Streams the same SSE events as /import. The existing dedup logic
    naturally only fetches PMIDs that aren't already in `article`, so
    the retry only does the unfinished work.
    """
    run = db.query(ArticleImportRun).filter_by(run_id=run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Import run not found")
    if run.status not in ("PARTIAL", "FAILED"):
        raise HTTPException(
            status_code=400,
            detail=f"Run {run_id} is {run.status}; only PARTIAL/FAILED runs can be retried",
        )
    if not run.file_id:
        raise HTTPException(status_code=400, detail="Run has no staged file to retry from")
    try:
        validate_file_id(run.file_id)
    except HTTPException:
        raise HTTPException(status_code=400, detail="Run has an invalid file_id")
    filepath = os.path.join(UPLOAD_DIR, run.file_id)
    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=410,
            detail="Staged file is no longer available. Please re-upload to retry.",
        )

    rename_map = {
        m["original"]: m["canonical"]
        for m in (run.mappings_json or [])
        if m.get("canonical")
    }
    import_gold_standard = bool(run.import_gold_standard)
    return StreamingResponse(
        _run_import_stream(
            run.file_id, rename_map, import_gold_standard, existing_run_id=run_id,
        ),
        media_type="text/event-stream",
    )


@router.post("/import-runs/{run_id}/dismiss")
def dismiss_import_run(run_id: int, db: Session = Depends(get_db)):
    """Discard a PARTIAL/FAILED run's staging file so it stops nagging.

    Idempotent: succeeds even if the file is already gone.
    """
    run = db.query(ArticleImportRun).filter_by(run_id=run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Import run not found")
    if run.file_id:
        try:
            validate_file_id(run.file_id)
            for p in (
                os.path.join(UPLOAD_DIR, run.file_id),
                os.path.join(UPLOAD_DIR, run.file_id + ".name"),
            ):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
        except HTTPException:
            pass
    run.file_id = None
    db.commit()
    return {"run_id": run_id, "dismissed": True}


@router.get("")
def list_articles_summary(db: Session = Depends(get_db)):
    from api.models import Identity
    from sqlalchemy import func, case

    rows = (
        db.query(
            PersonArticle.person_id,
            func.count(PersonArticle.pmid).label("article_count"),
            func.sum(case((PersonArticle.source == "upload", 1), else_=0)).label("uploaded"),
            func.sum(case((PersonArticle.source == "search", 1), else_=0)).label("retrieved"),
        )
        .group_by(PersonArticle.person_id)
        .all()
    )
    names = {
        i.person_id: {"first_name": i.first_name, "last_name": i.last_name}
        for i in db.query(Identity).all()
    }
    return [
        {
            "person_id": r.person_id,
            "first_name": names.get(r.person_id, {}).get("first_name", ""),
            "last_name": names.get(r.person_id, {}).get("last_name", ""),
            "article_count": r.article_count,
            "uploaded": int(r.uploaded or 0),
            "retrieved": int(r.retrieved or 0),
        }
        for r in rows
    ]


@router.get("/{person_id}")
def get_articles(person_id: str, db: Session = Depends(get_db)):
    results = (
        db.query(Article, PersonArticle)
        .join(PersonArticle, Article.pmid == PersonArticle.pmid)
        .filter(PersonArticle.person_id == person_id)
        .order_by(Article.pub_year.desc())
        .all()
    )
    return [
        {"pmid": r.Article.pmid, "title": r.Article.title, "journal": r.Article.journal,
         "pub_year": r.Article.pub_year, "source": r.PersonArticle.source}
        for r in results
    ]
