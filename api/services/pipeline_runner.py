# api/services/pipeline_runner.py
"""
Orchestrates the scoring pipeline for multiple researchers concurrently.
Wraps existing core/ and features/ modules.
"""
import asyncio
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from typing import AsyncGenerator

from sqlalchemy.orm import Session

from api.database import SessionLocal
from api.models import (
    Identity, Article, PersonArticle, PersonArticleScore, Curation,
)

# Add project root to path so core/ and features/ are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.identity import Identity as CoreIdentity
from core.article import Article as CoreArticle, Author
from core.pubmed import efetch, esearch
from core.target_author import find_target_author
from core.feature_generator import generate_features
from core.scoring import score_articles
from core.config import load_config

logger = logging.getLogger(__name__)

# Adaptive worker pool
MAX_WORKERS = min(4, (os.cpu_count() or 2))


def _db_identity_to_core(db_identity: Identity) -> CoreIdentity:
    """Convert SQLAlchemy Identity to core.identity.Identity dataclass."""
    return CoreIdentity(
        person_id=db_identity.person_id,
        first_name=db_identity.first_name,
        last_name=db_identity.last_name,
        middle_name=db_identity.middle_name or "",
        primary_email=db_identity.primary_email or "",
        primary_institution=db_identity.primary_institution or "",
        department=db_identity.department or "",
        title=db_identity.title or "",
        orcid=db_identity.orcid or "",
        bachelor_year=db_identity.bachelor_year or 0,
        doctoral_year=db_identity.doctoral_year or 0,
    )


def _db_article_to_core(db_article: Article) -> CoreArticle:
    """Convert SQLAlchemy Article to core.article.Article dataclass."""
    authors = []
    if db_article.authors:
        for a in db_article.authors:
            authors.append(Author(
                first_name=a.get("first_name", ""),
                last_name=a.get("last_name", ""),
                initials=a.get("initials", ""),
                affiliation=a.get("affiliation", ""),
                orcid=a.get("orcid", ""),
            ))
    return CoreArticle(
        pmid=db_article.pmid,
        title=db_article.title or "",
        journal=db_article.journal or "",
        pub_year=db_article.pub_year or 0,
        authors=authors,
        doi=db_article.doi or "",
        abstract=db_article.abstract_text or "",
        mesh_headings=db_article.mesh_headings or [],
        keywords=db_article.keywords or [],
        grants=db_article.grants or [],
        publication_types=db_article.publication_types or [],
    )


def _process_one_researcher(
    person_id: str,
    mode: str,
    config: dict,
    model_dir: str,
) -> dict:
    """
    Process a single researcher through the full pipeline.
    Runs in a thread. Returns a result dict.
    """
    db = SessionLocal()
    try:
        identity = db.query(Identity).filter_by(person_id=person_id).first()
        if not identity:
            return {"person_id": person_id, "error": "Identity not found"}

        core_identity = _db_identity_to_core(identity)
        api_key = os.environ.get("PUBMED_API_KEY")

        # Phase 1: Retrieve articles
        person_articles = db.query(PersonArticle).filter_by(person_id=person_id).all()
        existing_pmids = {pa.pmid for pa in person_articles}

        if mode == "full" and not existing_pmids:
            # Search PubMed by name
            search_pmids = esearch(
                first_name=core_identity.first_name,
                last_name=core_identity.last_name,
                api_key=api_key,
            )
            new_pmids = [p for p in search_pmids if p not in existing_pmids]
            if new_pmids:
                articles = efetch(new_pmids, api_key=api_key)
                for art in articles:
                    existing_art = db.query(Article).filter_by(pmid=art.pmid).first()
                    if not existing_art:
                        db.add(Article(
                            pmid=art.pmid,
                            title=art.title,
                            journal=art.journal,
                            pub_year=art.pub_year,
                            doi=art.doi,
                            abstract_text=art.abstract,
                            authors=[{
                                "first_name": a.first_name,
                                "last_name": a.last_name,
                                "initials": a.initials,
                                "affiliation": a.affiliation,
                                "orcid": a.orcid,
                            } for a in art.authors],
                            mesh_headings=art.mesh_headings if hasattr(art, 'mesh_headings') else [],
                            keywords=art.keywords if hasattr(art, 'keywords') else [],
                            grants=art.grants if hasattr(art, 'grants') else [],
                            publication_types=art.publication_types if hasattr(art, 'publication_types') else [],
                        ))
                    existing_pa = db.query(PersonArticle).filter_by(
                        person_id=person_id, pmid=art.pmid
                    ).first()
                    if not existing_pa:
                        db.add(PersonArticle(
                            person_id=person_id, pmid=art.pmid, source="search"
                        ))
                db.commit()

        # Reload all articles for this person
        person_articles = db.query(PersonArticle).filter_by(person_id=person_id).all()
        pmids = [pa.pmid for pa in person_articles]
        db_articles = db.query(Article).filter(Article.pmid.in_(pmids)).all() if pmids else []
        core_articles = [_db_article_to_core(a) for a in db_articles]

        if not core_articles:
            return {
                "person_id": person_id,
                "article_count": 0,
                "scored_count": 0,
            }

        # Phase 2: Target author matching
        for art in core_articles:
            idx = find_target_author(art, core_identity)
            art.target_author_index = idx
            # Update DB
            pa = db.query(PersonArticle).filter_by(
                person_id=person_id, pmid=art.pmid
            ).first()
            if pa:
                pa.target_author_index = idx
        db.commit()

        # Phase 3: Feature generation
        curations = db.query(Curation).filter_by(person_id=person_id).all()
        has_curations = len(curations) > 0

        feature_rows = generate_features(
            identity=core_identity,
            articles=core_articles,
            config=config,
            curated_articles=core_articles if has_curations else None,
            curations={c.pmid: c.assertion for c in curations} if has_curations else None,
        )

        if not feature_rows:
            return {
                "person_id": person_id,
                "article_count": len(core_articles),
                "scored_count": 0,
            }

        # Phase 4: Scoring
        model_type = "feedbackIdentity" if has_curations else "identityOnly"
        scored_df = score_articles(feature_rows, model_type=model_type, model_dir=model_dir)

        # Save scores
        for _, row in scored_df.iterrows():
            pmid = str(row["pmid"])
            existing_score = db.query(PersonArticleScore).filter_by(
                person_id=person_id, pmid=pmid, model_type=model_type
            ).first()
            score_val = float(row.get("calibrated_score", 0))
            features_dict = {
                k: float(v) if isinstance(v, (int, float)) else v
                for k, v in row.items() if k not in ("pmid", "calibrated_score", "raw_score")
            }
            if existing_score:
                existing_score.calibrated_score = score_val
                existing_score.raw_score = float(row.get("raw_score", 0))
                existing_score.features = features_dict
            else:
                db.add(PersonArticleScore(
                    person_id=person_id,
                    pmid=pmid,
                    model_type=model_type,
                    calibrated_score=score_val,
                    raw_score=float(row.get("raw_score", 0)),
                    features=features_dict,
                ))
        db.commit()

        return {
            "person_id": person_id,
            "article_count": len(core_articles),
            "scored_count": len(scored_df),
            "score_min": float(scored_df["calibrated_score"].min()),
            "score_max": float(scored_df["calibrated_score"].max()),
        }
    except Exception as e:
        logger.exception(f"Error processing {person_id}")
        return {"person_id": person_id, "error": str(e)}
    finally:
        db.close()


async def run_pipeline(
    person_ids: list[str],
    mode: str = "full",
) -> AsyncGenerator[dict, None]:
    """
    Run the scoring pipeline for multiple researchers concurrently.
    Yields progress events as dicts.
    mode: "full" (retrieve + score) or "score_only" (score uploaded articles)
    """
    config = load_config()
    model_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "models", "wcm",
    )

    total = len(person_ids)
    completed = 0

    yield {
        "type": "started",
        "total": total,
        "mode": mode,
    }

    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    # Submit all tasks
    futures = {}
    for pid in person_ids:
        future = loop.run_in_executor(
            executor, _process_one_researcher, pid, mode, config, model_dir
        )
        futures[pid] = future
        yield {
            "type": "queued",
            "person_id": pid,
        }

    # Collect results as they complete
    for pid in person_ids:
        yield {
            "type": "processing",
            "person_id": pid,
            "phase": "running",
        }
        result = await futures[pid]
        completed += 1
        yield {
            "type": "complete_one",
            "person_id": pid,
            "completed": completed,
            "total": total,
            **result,
        }

    executor.shutdown(wait=False)
    yield {
        "type": "finished",
        "completed": completed,
        "total": total,
    }
