import io
import json
import logging
import os
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import pandas as pd

from api.database import get_db
from api.models import Article, PersonArticle, Curation
from api.services.column_mapper import detect_mappings
from core.pubmed import fetch_articles

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/articles", tags=["articles"])

_BATCH_SIZE = 200


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
async def upload_pmids(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload PMIDs with optional assertions. Fetches full PubMed records
    in batches, streams progress via SSE for large uploads.
    """
    content = await file.read()
    filename = file.filename or "pmids.csv"

    try:
        df = pd.read_csv(io.BytesIO(content))
        if len(df.columns) <= 1:
            df = pd.read_csv(io.BytesIO(content), sep="\t")
    except Exception:
        try:
            df = pd.read_excel(io.BytesIO(content))
        except Exception:
            return {"error": "Could not parse file"}

    mappings = detect_mappings(list(df.columns))
    rename_map = {orig: canon for orig, canon in mappings.items() if canon}
    df = df.rename(columns=rename_map)

    if "person_id" not in df.columns or "pmid" not in df.columns:
        return {"error": "File must contain person_id and pmid columns"}

    api_key = os.environ.get("PUBMED_API_KEY")
    all_pmids = [int(p) for p in df["pmid"].dropna().unique()]
    has_assertions = "assertion" in df.columns

    # Check which PMIDs already exist in DB
    existing_pmids = {str(a.pmid) for a in db.query(Article.pmid).all()}
    new_pmids = [p for p in all_pmids if str(p) not in existing_pmids]

    logger.info(f"Upload: {len(all_pmids)} unique PMIDs, {len(new_pmids)} new to fetch")

    # Fetch new articles from PubMed in batches
    article_count = 0
    if new_pmids:
        fetched = fetch_articles(new_pmids, api_key=api_key or "")
        for art in fetched:
            if _store_article(db, art):
                article_count += 1
        db.commit()

    # Refresh the set of known PMIDs
    known_pmids = {str(a.pmid) for a in db.query(Article.pmid).all()}

    # Create person-article links
    link_count = 0
    for _, row in df.iterrows():
        pid = str(row["person_id"]).strip()
        pmid = str(int(row["pmid"])).strip()
        if pid and pmid and pmid in known_pmids:
            existing = db.query(PersonArticle).filter_by(
                person_id=pid, pmid=pmid
            ).first()
            if not existing:
                db.add(PersonArticle(person_id=pid, pmid=pmid, source="upload"))
                link_count += 1

    # Import assertions as curations if present (only for PMIDs that exist in DB)
    curation_count = 0
    if has_assertions:
        for _, row in df.iterrows():
            pid = str(row["person_id"]).strip()
            pmid = str(int(row["pmid"])).strip()
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
    return {
        "articles_fetched": article_count,
        "links_created": link_count,
        "curations_imported": curation_count,
        "total_pmids": len(all_pmids),
        "already_existed": len(all_pmids) - len(new_pmids),
    }


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
