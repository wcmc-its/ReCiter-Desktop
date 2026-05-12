import io
import os
import tempfile
import uuid
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
import pandas as pd

from api.database import get_db
from api.models import Identity, PersonArticle, PersonArticleScore, Curation
from api.services.column_mapper import detect_mappings
from api.services.upload_utils import (
    UPLOAD_DIR,
    save_upload_streaming,
    upload_path,
)

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
