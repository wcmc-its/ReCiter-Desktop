"""Application-level reset.

A first-class "start over" path for users who loaded test/demo data and
want a clean slate without dropping the docker volume from a terminal.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import (
    Article,
    Curation,
    Identity,
    Institution,
    PersonArticle,
    PersonArticleScore,
    PipelineRun,
    RetrievalLog,
)

router = APIRouter(prefix="/api", tags=["admin"])


@router.post("/reset")
def reset_application(db: Session = Depends(get_db)):
    """Wipe all user data: institution config, researchers, articles,
    scores, curations, retrieval history, pipeline runs.

    Children deleted before parents to avoid foreign-key complaints —
    FK cascades cover most of it, but we delete explicitly so the
    response counts each table.
    """
    counts = {
        "scores": db.query(PersonArticleScore).delete(synchronize_session=False),
        "curations": db.query(Curation).delete(synchronize_session=False),
        "person_articles": db.query(PersonArticle).delete(synchronize_session=False),
        "retrieval_logs": db.query(RetrievalLog).delete(synchronize_session=False),
        "pipeline_runs": db.query(PipelineRun).delete(synchronize_session=False),
        "articles": db.query(Article).delete(synchronize_session=False),
        "identities": db.query(Identity).delete(synchronize_session=False),
        "institution": db.query(Institution).delete(synchronize_session=False),
    }
    db.commit()
    return {"status": "ok", "deleted": counts}
