import io
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
import pandas as pd

from api.database import SessionLocal, get_db
from api.models import Article, Identity, PersonArticle, PersonArticleScore, Curation
from api.routers.articles import _store_article
from api.services.column_mapper import detect_mappings
from api.services.upload_utils import (
    UPLOAD_DIR,
    save_upload_streaming,
    upload_path,
)
from core.pubmed import fetch_articles

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/researchers", tags=["researchers"])


class ColumnMapping(BaseModel):
    original: str
    canonical: str | None


class ImportRequest(BaseModel):
    mappings: list[ColumnMapping]
    file_id: str
    import_gold_standard: bool = False


def _read_full(content: bytes, filename: str) -> pd.DataFrame:
    if filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(content))
    if filename.endswith(".tsv"):
        return pd.read_csv(io.BytesIO(content), sep="\t")
    return pd.read_csv(io.BytesIO(content))


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_id = f"upload_{uuid.uuid4().hex[:12]}"
    filepath = upload_path(file_id)
    content = await save_upload_streaming(file, filepath)

    filename = file.filename or "upload.csv"
    # Single full parse — derive headers, preview, gold-standard count,
    # and row count from one DataFrame instead of reparsing 3-4 times.
    df = _read_full(content, filename)

    headers = list(df.columns)
    mappings = detect_mappings(headers)
    preview_rows = df.head(3).fillna("").to_dict(orient="records")

    has_gold_standard = (
        any(mappings.get(h) == "pmid" for h in headers)
        and any(mappings.get(h) == "assertion" for h in headers)
    )
    gold_standard_count = 0
    if has_gold_standard:
        assertion_col = next(h for h in headers if mappings.get(h) == "assertion")
        gold_standard_count = int(df[assertion_col].notna().sum())

    return {
        "file_id": file_id,
        "filename": filename,
        "row_count": int(len(df)),
        "mappings": [
            {"original": h, "canonical": mappings.get(h), "sample": str(preview_rows[0].get(h, "")) if preview_rows else ""}
            for h in headers
        ],
        "preview": preview_rows,
        "has_gold_standard": has_gold_standard,
        "gold_standard_count": gold_standard_count,
    }


@router.post("/import")
def import_researchers(req: ImportRequest, db: Session = Depends(get_db)):
    filepath = upload_path(req.file_id)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Upload not found. Please re-upload the file.")
    with open(filepath, "rb") as f:
        content = f.read()

    rename_map = {m.original: m.canonical for m in req.mappings if m.canonical}

    # Try CSV first (most common), then Excel
    try:
        df = pd.read_csv(io.BytesIO(content))
        if len(df.columns) <= 1:
            # Might be TSV
            df = pd.read_csv(io.BytesIO(content), sep="\t")
    except Exception:
        try:
            df = pd.read_excel(io.BytesIO(content))
        except Exception:
            raise HTTPException(status_code=400, detail="Could not parse file. Supported formats: CSV, TSV, Excel.")

    df = df.rename(columns=rename_map)
    df = df.fillna("")

    identity_count = 0
    for _, row in df.iterrows():
        pid = str(row.get("person_id", "")).strip()
        fname = str(row.get("first_name", "")).strip()
        lname = str(row.get("last_name", "")).strip()
        if not pid or not fname or not lname:
            continue

        existing = db.query(Identity).filter_by(person_id=pid).first()
        if existing:
            existing.first_name = fname
            existing.last_name = lname
            existing.middle_name = str(row.get("middle_name", "")).strip()
            existing.primary_email = str(row.get("primary_email", "")).strip()
            existing.primary_institution = str(row.get("primary_institution", "")).strip()
            existing.department = str(row.get("department", "")).strip()
            existing.title = str(row.get("title", "")).strip()
            existing.orcid = str(row.get("orcid", "")).strip()
            existing.bachelor_year = int(row.get("bachelor_year", 0) or 0)
            existing.doctoral_year = int(row.get("doctoral_year", 0) or 0)
        else:
            db.add(Identity(
                person_id=pid, first_name=fname, last_name=lname,
                middle_name=str(row.get("middle_name", "")).strip(),
                primary_email=str(row.get("primary_email", "")).strip(),
                primary_institution=str(row.get("primary_institution", "")).strip(),
                department=str(row.get("department", "")).strip(),
                title=str(row.get("title", "")).strip(),
                orcid=str(row.get("orcid", "")).strip(),
                bachelor_year=int(row.get("bachelor_year", 0) or 0),
                doctoral_year=int(row.get("doctoral_year", 0) or 0),
            ))
        identity_count += 1

    curation_count = 0
    if req.import_gold_standard and "pmid" in df.columns and "assertion" in df.columns:
        for _, row in df.iterrows():
            pid = str(row.get("person_id", "")).strip()
            pmid = str(row.get("pmid", "")).strip()
            assertion = str(row.get("assertion", "")).strip().upper()
            if pid and pmid and assertion in ("ACCEPTED", "REJECTED"):
                existing_cur = db.query(Curation).filter_by(person_id=pid, pmid=pmid).first()
                if not existing_cur:
                    db.add(Curation(person_id=pid, pmid=pmid, assertion=assertion, source="import"))
                    curation_count += 1

    db.commit()
    os.remove(filepath)

    return {"identity_count": identity_count, "curation_count": curation_count}


SAMPLE_DIR = Path(__file__).resolve().parents[2] / "frontend" / "public" / "sample"


def _upsert_identity(db: Session, row: dict) -> bool:
    pid = str(row.get("person_id", "")).strip()
    fname = str(row.get("first_name", "")).strip()
    lname = str(row.get("last_name", "")).strip()
    if not pid or not fname or not lname:
        return False

    fields = dict(
        first_name=fname,
        last_name=lname,
        middle_name=str(row.get("middle_name", "")).strip(),
        primary_email=str(row.get("primary_email", "")).strip(),
        primary_institution=str(row.get("primary_institution", "")).strip(),
        department=str(row.get("department", "")).strip(),
        title=str(row.get("title", "")).strip(),
        orcid=str(row.get("orcid", "")).strip(),
        bachelor_year=int(row.get("bachelor_year", 0) or 0),
        doctoral_year=int(row.get("doctoral_year", 0) or 0),
    )

    existing = db.query(Identity).filter_by(person_id=pid).first()
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
    else:
        db.add(Identity(person_id=pid, **fields))
    return True


@router.post("/load-sample")
def load_sample():
    """Stream the bundled sample roster + assertions (5 WCM researchers).

    Phase 1: upsert identities.
    Phase 2: fetch any missing PMIDs from PubMed in batches.
    Phase 3: link person_article rows and import curation assertions.

    Emits the same SSE event shape as /api/articles/import so the frontend
    can reuse the existing progress UI. Merges into existing tables — does
    not clear anything.
    """
    researchers_path = SAMPLE_DIR / "sample-researchers.csv"
    articles_path = SAMPLE_DIR / "sample-articles.csv"
    if not researchers_path.exists() or not articles_path.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                "Sample data files are missing. Run scripts/build_sample_data.py "
                "to regenerate them."
            ),
        )

    def event_stream():
        db = SessionLocal()
        try:
            try:
                yield f"data: {json.dumps({'type': 'status', 'message': 'Loading sample researchers...'})}\n\n"
                r_df = pd.read_csv(researchers_path).fillna("")
                a_df = pd.read_csv(articles_path).fillna("")

                identity_count = 0
                for _, row in r_df.iterrows():
                    if _upsert_identity(db, row.to_dict()):
                        identity_count += 1
                db.commit()
                yield f"data: {json.dumps({'type': 'status', 'message': f'{identity_count} researchers loaded'})}\n\n"

                # PubMed API key may not be set yet (institutional profile
                # is required before this button is shown, but the key is
                # optional within profile setup). Pass empty string and
                # PubMed will throttle to 3 req/sec instead of 10.
                from api.routers.institution import get_pubmed_api_key
                api_key = get_pubmed_api_key(db) or ""

                try:
                    all_pmids = [int(p) for p in a_df["pmid"].astype(int).unique()]
                except (ValueError, TypeError) as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Invalid PMID in sample data: {e}'})}\n\n"
                    return

                existing_pmids = {str(a.pmid) for a in db.query(Article.pmid).all()}
                new_pmids = [p for p in all_pmids if str(p) not in existing_pmids]
                already_existed = len(all_pmids) - len(new_pmids)
                yield f"data: {json.dumps({'type': 'status', 'message': f'{len(all_pmids)} unique PMIDs ({already_existed} already on file, {len(new_pmids)} to fetch)'})}\n\n"

                progress_events: list[dict] = []

                def on_batch(event: dict):
                    progress_events.append(event)

                article_count = 0
                if new_pmids:
                    yield f"data: {json.dumps({'type': 'status', 'message': 'Fetching metadata from PubMed...'})}\n\n"
                    CHUNK = 200
                    chunks = [new_pmids[i:i + CHUNK] for i in range(0, len(new_pmids), CHUNK)]
                    requested_total = 0
                    for chunk_idx, chunk in enumerate(chunks, start=1):
                        progress_events.clear()
                        fetched = fetch_articles(chunk, api_key=api_key, on_batch=on_batch)
                        for art in fetched:
                            if _store_article(db, art):
                                article_count += 1
                        db.commit()
                        requested_total += len(chunk)
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
                for _, row in a_df.iterrows():
                    pid = str(row.get("person_id", "")).strip()
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

                yield f"data: {json.dumps({'type': 'status', 'message': 'Importing curated assertions...'})}\n\n"
                curation_count = 0
                for _, row in a_df.iterrows():
                    pid = str(row.get("person_id", "")).strip()
                    try:
                        pmid = str(int(row["pmid"])).strip()
                    except (ValueError, TypeError):
                        continue
                    assertion = str(row.get("assertion", "")).strip().upper()
                    if pid and pmid and pmid in known_pmids and assertion in ("ACCEPTED", "REJECTED"):
                        existing_cur = db.query(Curation).filter_by(person_id=pid, pmid=pmid).first()
                        if not existing_cur:
                            db.add(Curation(
                                person_id=pid, pmid=pmid,
                                assertion=assertion, source="import",
                            ))
                            curation_count += 1

                db.commit()

                yield (
                    "data: "
                    + json.dumps({
                        "type": "complete",
                        "identity_count": identity_count,
                        "articles_fetched": article_count,
                        "links_created": link_count,
                        "curations_imported": curation_count,
                        "total_pmids": len(all_pmids),
                        "already_existed": already_existed,
                    })
                    + "\n\n"
                )
            except Exception as exc:
                logger.exception("Sample data load failed")
                try:
                    db.rollback()
                except Exception:
                    pass
                yield f"data: {json.dumps({'type': 'error', 'message': f'Load failed: {exc}'})}\n\n"
        finally:
            db.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("")
def list_researchers(db: Session = Depends(get_db)):
    identities = db.query(Identity).order_by(Identity.last_name).all()
    article_counts = dict(
        db.query(PersonArticle.person_id, func.count(PersonArticle.pmid))
        .group_by(PersonArticle.person_id).all()
    )
    score_counts = dict(
        db.query(PersonArticleScore.person_id, func.count(PersonArticleScore.pmid))
        .group_by(PersonArticleScore.person_id).all()
    )
    return [
        {
            "person_id": i.person_id,
            "first_name": i.first_name,
            "last_name": i.last_name,
            "middle_name": i.middle_name,
            "primary_email": i.primary_email,
            "primary_institution": i.primary_institution,
            "department": i.department,
            "title": i.title,
            "orcid": i.orcid,
            "doctoral_year": i.doctoral_year,
            "article_count": article_counts.get(i.person_id, 0),
            "score_count": score_counts.get(i.person_id, 0),
        }
        for i in identities
    ]


@router.get("/{person_id}")
def get_researcher(person_id: str, db: Session = Depends(get_db)):
    identity = db.query(Identity).filter_by(person_id=person_id).first()
    if not identity:
        raise HTTPException(status_code=404, detail="Researcher not found")
    return {
        "person_id": identity.person_id,
        "first_name": identity.first_name,
        "last_name": identity.last_name,
        "middle_name": identity.middle_name,
        "primary_email": identity.primary_email,
        "primary_institution": identity.primary_institution,
        "department": identity.department,
        "title": identity.title,
        "orcid": identity.orcid,
        "bachelor_year": identity.bachelor_year,
        "doctoral_year": identity.doctoral_year,
    }
