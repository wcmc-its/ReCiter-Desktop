import json
from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.database import get_db, SessionLocal
from api.models import Identity, PipelineRun
from api.services.pipeline_runner import run_pipeline

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


class PipelineRequest(BaseModel):
    person_ids: list[str] | None = None
    mode: str = "full"


@router.post("/run")
async def run(req: PipelineRequest, db: Session = Depends(get_db)):
    if req.person_ids:
        person_ids = req.person_ids
    else:
        identities = db.query(Identity.person_id).all()
        person_ids = [i.person_id for i in identities]

    if not person_ids:
        return {"error": "No researchers found"}

    # Create pipeline_run row (PENDING) before streaming (per D-05)
    pipeline_run = PipelineRun(
        mode=req.mode,
        status="PENDING",
        total_researchers=len(person_ids),
    )
    db.add(pipeline_run)
    db.commit()
    db.refresh(pipeline_run)
    run_id = pipeline_run.run_id

    async def event_stream():
        succeeded = 0
        failed = 0
        total_articles = 0
        async for event in run_pipeline(person_ids, mode=req.mode, run_id=run_id):
            # Track run status from events
            if event.get("type") == "started":
                # Transition to RUNNING (per D-05)
                update_db = SessionLocal()
                try:
                    run_row = update_db.query(PipelineRun).filter_by(run_id=run_id).first()
                    if run_row:
                        run_row.status = "RUNNING"
                        run_row.started_at = datetime.utcnow()
                    update_db.commit()
                finally:
                    update_db.close()
            elif event.get("type") == "complete_one":
                if event.get("error"):
                    failed += 1
                else:
                    succeeded += 1
                    total_articles += event.get("article_count", 0)
            elif event.get("type") == "finished":
                # Transition to COMPLETED (per D-06)
                update_db = SessionLocal()
                try:
                    run_row = update_db.query(PipelineRun).filter_by(run_id=run_id).first()
                    if run_row:
                        run_row.status = "COMPLETED"
                        run_row.completed_at = datetime.utcnow()
                        run_row.researchers_succeeded = succeeded
                        run_row.researchers_failed = failed
                        run_row.total_articles = total_articles
                    update_db.commit()
                finally:
                    update_db.close()
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def get_assertion_count(db: Session) -> int:
    """Count distinct (person_id, pmid) pairs with both a score and a curation."""
    from api.models import PersonArticleScore, Curation
    return (
        db.query(PersonArticleScore.person_id, PersonArticleScore.pmid)
        .join(
            Curation,
            (PersonArticleScore.person_id == Curation.person_id) &
            (PersonArticleScore.pmid == Curation.pmid)
        )
        .distinct()
        .count()
    )


@router.get("/status")
def status(db: Session = Depends(get_db)):
    from sqlalchemy import func
    from api.models import PersonArticle, PersonArticleScore

    total_researchers = db.query(Identity).count()
    total_articles = db.query(PersonArticle).count()
    uploaded_articles = db.query(PersonArticle).filter(PersonArticle.source == "upload").count()
    searched_articles = db.query(PersonArticle).filter(PersonArticle.source == "search").count()
    total_scores = db.query(PersonArticleScore).count()
    scored_researchers = db.query(PersonArticleScore.person_id).distinct().count()

    # Score distribution for summary stats
    high_confidence = 0
    review_band = 0
    unlikely = 0
    if total_scores > 0:
        high_confidence = db.query(PersonArticleScore).filter(
            PersonArticleScore.calibrated_score >= 0.95
        ).count()
        unlikely = db.query(PersonArticleScore).filter(
            PersonArticleScore.calibrated_score < 0.30
        ).count()
        review_band = total_scores - high_confidence - unlikely

    assertion_count = get_assertion_count(db)

    from api.models import RetrievalLog
    last_retrieval = db.query(func.max(RetrievalLog.last_retrieval_date)).scalar()
    last_retrieval_str = last_retrieval.isoformat() if last_retrieval else None

    return {
        "total_researchers": total_researchers,
        "total_articles": total_articles,
        "uploaded_articles": uploaded_articles,
        "searched_articles": searched_articles,
        "total_scores": total_scores,
        "scored_researchers": scored_researchers,
        "high_confidence": high_confidence,
        "review_band": review_band,
        "unlikely": unlikely,
        "assertion_count": assertion_count,
        "last_retrieval_date": last_retrieval_str,
    }
