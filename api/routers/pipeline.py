import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Identity
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

    async def event_stream():
        async for event in run_pipeline(person_ids, mode=req.mode):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/status")
def status(db: Session = Depends(get_db)):
    from sqlalchemy import func
    from api.models import PersonArticle, PersonArticleScore

    total_researchers = db.query(Identity).count()
    total_articles = db.query(PersonArticle).count()
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

    return {
        "total_researchers": total_researchers,
        "total_articles": total_articles,
        "total_scores": total_scores,
        "scored_researchers": scored_researchers,
        "high_confidence": high_confidence,
        "review_band": review_band,
        "unlikely": unlikely,
    }
