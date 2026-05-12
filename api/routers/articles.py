import io
import json
import logging
import os
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import pandas as pd

from api.database import SessionLocal, get_db
from api.models import Article, PersonArticle, Curation
from api.services.column_mapper import detect_mappings
from core.pubmed import fetch_articles

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/articles", tags=["articles"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


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
    """Store a core.Article to the DB. Returns True if new."""
    pmid_str = str(art.pmid)
    existing = db.query(Article).filter_by(pmid=pmid_str).first()
    if existing:
        return False
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


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Stage a file: parse headers, detect column mappings, return a preview.

    No DB writes happen here. Caller must follow up with POST /import.
    """
    content = await file.read()
    filename = file.filename or "pmids.csv"

    file_id = f"articles_{uuid.uuid4().hex[:12]}"
    filepath = os.path.join(UPLOAD_DIR, file_id)
    with open(filepath, "wb") as f:
        f.write(content)
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


@router.post("/import")
def import_articles(req: ImportRequest):
    """Import staged PMIDs with SSE progress events.

    Stream events (newline-delimited `data: {json}\\n\\n`):
      - {type: "status", message}
      - {type: "fetch_progress", batch, batches, fetched, total, error?}
      - {type: "complete", articles_fetched, links_created, curations_imported,
                            total_pmids, already_existed}
      - {type: "error", message}
    """
    filepath = os.path.join(UPLOAD_DIR, req.file_id)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Upload not found. Please re-upload the file.")

    with open(filepath, "rb") as f:
        content = f.read()
    name_path = filepath + ".name"
    filename = "pmids.csv"
    if os.path.exists(name_path):
        with open(name_path) as f:
            filename = f.read().strip() or filename

    rename_map = {m.original: m.canonical for m in req.mappings if m.canonical}

    def event_stream():
        db = SessionLocal()
        try:
            yield f"data: {json.dumps({'type': 'status', 'message': 'Reading file...'})}\n\n"

            try:
                df = _read_dataframe(content, filename)
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Could not parse file: {e}'})}\n\n"
                return

            df = df.rename(columns=rename_map)

            if "person_id" not in df.columns or "pmid" not in df.columns:
                yield f"data: {json.dumps({'type': 'error', 'message': 'File must map both person_id and pmid columns.'})}\n\n"
                return

            from api.routers.institution import get_pubmed_api_key
            api_key = get_pubmed_api_key(db)

            df = df.dropna(subset=["pmid"])
            try:
                all_pmids = [int(p) for p in df["pmid"].astype(int).unique()]
            except (ValueError, TypeError) as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Invalid PMID value: {e}'})}\n\n"
                return

            has_assertions = req.import_gold_standard and "assertion" in df.columns

            existing_pmids = {str(a.pmid) for a in db.query(Article.pmid).all()}
            new_pmids = [p for p in all_pmids if str(p) not in existing_pmids]
            already_existed = len(all_pmids) - len(new_pmids)

            yield f"data: {json.dumps({'type': 'status', 'message': f'{len(all_pmids)} unique PMIDs ({already_existed} already on file, {len(new_pmids)} to fetch)'})}\n\n"

            # Collect per-batch progress events from the synchronous fetcher.
            progress_events: list[dict] = []

            def on_batch(event: dict):
                progress_events.append(event)

            article_count = 0
            if new_pmids:
                yield f"data: {json.dumps({'type': 'status', 'message': 'Fetching metadata from PubMed...'})}\n\n"
                # Run fetch in chunks so we can flush progress between batches.
                # core.pubmed already batches internally, but the on_batch callback
                # is invoked after each one — we collect them inside the closure
                # and yield them on the next iteration.
                CHUNK = 200
                chunks = [new_pmids[i:i + CHUNK] for i in range(0, len(new_pmids), CHUNK)]
                fetched_total = 0
                for chunk_idx, chunk in enumerate(chunks, start=1):
                    progress_events.clear()
                    fetched = fetch_articles(chunk, api_key=api_key or "", on_batch=on_batch)
                    for art in fetched:
                        if _store_article(db, art):
                            article_count += 1
                    db.commit()
                    fetched_total += len(fetched)
                    # Flush any per-batch events from the fetcher (one per chunk here)
                    for ev in progress_events:
                        merged = {
                            "type": "fetch_progress",
                            "batch": chunk_idx,
                            "batches": len(chunks),
                            "fetched": fetched_total,
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

            # Clean up staging files
            try:
                os.remove(filepath)
                if os.path.exists(name_path):
                    os.remove(name_path)
            except OSError:
                pass

            yield f"data: {json.dumps({'type': 'complete', 'articles_fetched': article_count, 'links_created': link_count, 'curations_imported': curation_count, 'total_pmids': len(all_pmids), 'already_existed': already_existed})}\n\n"
        finally:
            db.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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
