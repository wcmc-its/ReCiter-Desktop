from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.database import get_db
from api.services.stats_service import compute_stats

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def get_stats(db: Session = Depends(get_db)):
    return compute_stats(db)
