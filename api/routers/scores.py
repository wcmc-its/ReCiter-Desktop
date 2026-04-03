import csv
import io
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Identity, Article, PersonArticle, PersonArticleScore

router = APIRouter(prefix="/api/scores", tags=["scores"])


@router.get("/export")
def export_scores(
    person_id: str | None = Query(None),
    threshold: int = Query(0),
    db: Session = Depends(get_db),
):
    query = (
        db.query(PersonArticleScore, Article, Identity)
        .join(Article, PersonArticleScore.pmid == Article.pmid)
        .join(Identity, PersonArticleScore.person_id == Identity.person_id)
    )
    if person_id:
        query = query.filter(PersonArticleScore.person_id == person_id)

    results = query.order_by(
        PersonArticleScore.person_id,
        PersonArticleScore.calibrated_score.desc(),
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "person_id", "first_name", "last_name", "pmid",
        "title", "journal", "year", "score", "pubmed_url",
    ])

    for r in results:
        score = round(r.PersonArticleScore.calibrated_score * 100) if r.PersonArticleScore.calibrated_score else 0
        if score >= threshold:
            writer.writerow([
                r.Identity.person_id, r.Identity.first_name, r.Identity.last_name,
                r.PersonArticleScore.pmid, r.Article.title, r.Article.journal,
                r.Article.pub_year, score,
                f"https://pubmed.ncbi.nlm.nih.gov/{r.PersonArticleScore.pmid}/",
            ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reciter_scores.csv"},
    )


@router.get("/{person_id}")
def get_scores(person_id: str, db: Session = Depends(get_db)):
    scores = (
        db.query(PersonArticleScore, Article)
        .join(Article, PersonArticleScore.pmid == Article.pmid)
        .filter(PersonArticleScore.person_id == person_id)
        .order_by(PersonArticleScore.calibrated_score.desc())
        .all()
    )

    return [
        {
            "pmid": s.PersonArticleScore.pmid,
            "score": round(s.PersonArticleScore.calibrated_score * 100) if s.PersonArticleScore.calibrated_score else 0,
            "model_type": s.PersonArticleScore.model_type,
            "title": s.Article.title,
            "journal": s.Article.journal,
            "pub_year": s.Article.pub_year,
            "doi": s.Article.doi,
        }
        for s in scores
    ]
