import json
import os
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Institution
from api.services.institution_discovery import discover_institution, generate_keywords

router = APIRouter(prefix="/api/institution", tags=["institution"])


class DiscoverRequest(BaseModel):
    domain: str
    year_range: str | None = None


class InstitutionClassification(BaseModel):
    name: str
    classification: str
    keywords: str


class ConfigureRequest(BaseModel):
    institutions: list[InstitutionClassification]
    email_domains: list[str]
    institution_label: str


@router.post("/discover")
async def discover(req: DiscoverRequest):
    api_key = os.environ.get("PUBMED_API_KEY")

    async def event_stream():
        async for event in discover_institution(req.domain, req.year_range, api_key):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/configure")
def configure(req: ConfigureRequest, db: Session = Depends(get_db)):
    home_keywords = []
    collab_keywords = []
    for inst in req.institutions:
        if inst.classification == "home":
            home_keywords.append(inst.keywords)
        elif inst.classification == "collaborating":
            collab_keywords.append(inst.keywords)

    config_pairs = {
        "institution_label": req.institution_label,
        "email_suffixes": json.dumps(
            ["@" + d if not d.startswith("@") else d for d in req.email_domains]
        ),
        "home_institution_keywords": json.dumps(home_keywords),
        "collaborating_institution_keywords": json.dumps(collab_keywords),
    }

    for key, value in config_pairs.items():
        existing = db.query(Institution).filter_by(config_key=key).first()
        if existing:
            existing.config_value = value
        else:
            db.add(Institution(config_key=key, config_value=value))
    db.commit()

    return {"status": "ok", "config_keys": list(config_pairs.keys())}


def get_pubmed_api_key(db: Session) -> str:
    """Get PubMed API key: config DB first, then env var fallback."""
    row = db.query(Institution).filter_by(config_key="pubmed_api_key").first()
    if row and row.config_value:
        return row.config_value
    return os.environ.get("PUBMED_API_KEY", "")


@router.get("")
def get_config(db: Session = Depends(get_db)):
    rows = db.query(Institution).all()
    config = {}
    for row in rows:
        try:
            config[row.config_key] = json.loads(row.config_value)
        except (json.JSONDecodeError, TypeError):
            config[row.config_key] = row.config_value
    return config
