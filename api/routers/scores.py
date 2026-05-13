import csv
import io
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Identity, Article, PersonArticle, PersonArticleScore, Curation
from api.services.orcid_inference import infer_orcids
from api.services.version import get_version

router = APIRouter(prefix="/api/scores", tags=["scores"])


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _provenance_header() -> str:
    """One-line provenance comment written at the top of every CSV export.

    Lets a downstream consumer trace any artifact back to the code revision
    that produced it. `#`-prefixed so pandas / R / tidyverse readers can
    skip it via the standard `comment` parameter.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"# ReCiter Desktop {get_version()} | exported: {ts}\n"


def _safe_cell(v):
    """Prefix a leading single-quote to cells starting with characters
    Excel/Sheets would interpret as a formula. Free-text fields like
    Article.title come from PubMed and could in principle start with `=`
    or similar, leading to formula injection when the CSV is opened.
    """
    if isinstance(v, str) and v and v[0] in _FORMULA_PREFIXES:
        return "'" + v
    return v


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
    output.write(_provenance_header())
    writer = csv.writer(output)
    writer.writerow([
        "person_id", "first_name", "last_name", "pmid",
        "title", "journal", "year", "score", "pubmed_url",
    ])

    for r in results:
        score = round(r.PersonArticleScore.calibrated_score * 100, 1) if r.PersonArticleScore.calibrated_score else 0
        if score >= threshold:
            writer.writerow([_safe_cell(v) for v in (
                r.Identity.person_id, r.Identity.first_name, r.Identity.last_name,
                r.PersonArticleScore.pmid, r.Article.title, r.Article.journal,
                r.Article.pub_year, score,
                f"https://pubmed.ncbi.nlm.nih.gov/{r.PersonArticleScore.pmid}/",
            )])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reciter_scores.csv"},
    )


@router.get("/orcid-report")
def orcid_report(mode: str = "feedback", db: Session = Depends(get_db)):
    use_curations = mode == "feedback"
    results = infer_orcids(db, use_curations=use_curations)
    tier_counts = {}
    for r in results:
        t = r["confidence_tier"]
        tier_counts[t] = tier_counts.get(t, 0) + 1
    return {
        "total_with_orcid": len(results),
        "tier_counts": tier_counts,
        "inferences": results,
    }


@router.get("/orcid-report/export")
def export_orcid_report(mode: str = "feedback", db: Session = Depends(get_db)):
    use_curations = mode == "feedback"
    results = infer_orcids(db, use_curations=use_curations)
    output = io.StringIO()
    output.write(_provenance_header())
    writer = csv.writer(output)
    writer.writerow([
        "person_id", "first_name", "last_name", "inferred_orcid",
        "confidence_tier", "confidence_score",
        "accepted_articles", "rejected_articles", "total_articles",
        "identity_orcid", "orcid_matches_identity", "orcid_link",
    ])
    for r in results:
        writer.writerow([_safe_cell(v) for v in (
            r["person_id"], r["first_name"], r["last_name"], r["orcid"],
            r["confidence_tier"], r["confidence_score"],
            r["accepted_articles"], r["rejected_articles"], r["total_articles"],
            r["identity_orcid"], r["orcid_matches_identity"],
            f"https://orcid.org/{r['orcid']}",
        )])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orcid_inference.csv"},
    )


@router.get("/{person_id}")
def get_scores(person_id: str, db: Session = Depends(get_db)):
    scores = (
        db.query(PersonArticleScore, Article, Curation)
        .join(Article, PersonArticleScore.pmid == Article.pmid)
        .outerjoin(
            Curation,
            (PersonArticleScore.person_id == Curation.person_id)
            & (PersonArticleScore.pmid == Curation.pmid),
        )
        .filter(PersonArticleScore.person_id == person_id)
        .order_by(PersonArticleScore.calibrated_score.desc())
        .all()
    )

    return [
        {
            "pmid": s.PersonArticleScore.pmid,
            "score": round(s.PersonArticleScore.calibrated_score * 100, 1) if s.PersonArticleScore.calibrated_score else 0,
            "model_type": s.PersonArticleScore.model_type,
            "title": s.Article.title,
            "journal": s.Article.journal,
            "pub_year": s.Article.pub_year,
            "doi": s.Article.doi,
            "features": s.PersonArticleScore.features or {},
            "assertion": s.Curation.assertion if s.Curation else None,
        }
        for s in scores
    ]
