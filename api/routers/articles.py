import io
import os
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session
import pandas as pd

from api.database import get_db
from api.models import Article, PersonArticle
from api.services.column_mapper import detect_mappings
from core.pubmed import fetch_articles

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.post("/upload")
async def upload_pmids(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    filename = file.filename or "pmids.csv"

    if filename.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content))
    elif filename.endswith(".tsv"):
        df = pd.read_csv(io.BytesIO(content), sep="\t")
    else:
        df = pd.read_csv(io.BytesIO(content))

    mappings = detect_mappings(list(df.columns))
    rename_map = {orig: canon for orig, canon in mappings.items() if canon}
    df = df.rename(columns=rename_map)

    if "person_id" not in df.columns or "pmid" not in df.columns:
        return {"error": "File must contain person_id and pmid columns"}

    api_key = os.environ.get("PUBMED_API_KEY")
    pmid_list = [str(p) for p in df["pmid"].dropna().unique()]

    articles = fetch_articles([int(p) for p in pmid_list], api_key=api_key or "")
    article_count = 0

    for art in articles:
        existing = db.query(Article).filter_by(pmid=art.pmid).first()
        if not existing:
            db.add(Article(
                pmid=art.pmid, title=art.title, journal=art.journal,
                pub_year=art.pub_year, doi=art.doi, abstract_text=art.abstract,
                authors=[{
                    "first_name": a.first_name, "last_name": a.last_name,
                    "initials": a.initials, "affiliation": a.affiliation,
                    "orcid": a.orcid,
                } for a in art.authors],
            ))
            article_count += 1

    link_count = 0
    for _, row in df.iterrows():
        pid = str(row["person_id"]).strip()
        pmid = str(row["pmid"]).strip()
        if pid and pmid:
            existing = db.query(PersonArticle).filter_by(person_id=pid, pmid=pmid).first()
            if not existing:
                db.add(PersonArticle(person_id=pid, pmid=pmid, source="upload"))
                link_count += 1

    db.commit()
    return {"articles_fetched": article_count, "links_created": link_count, "total_pmids": len(pmid_list)}


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
