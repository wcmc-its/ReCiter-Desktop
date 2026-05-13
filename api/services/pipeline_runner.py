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
import threading
from asyncio import as_completed as _as_completed
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import AsyncGenerator

from sqlalchemy.orm import Session

from api.database import SessionLocal
from api.models import (
    Identity, Article, PersonArticle, PersonArticleScore, Curation, RetrievalLog,
)
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy import text

# Add project root to path so core/ and features/ are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.identity import Identity as CoreIdentity
from core.article import Article as CoreArticle, Author, MeshHeading
from core.pubmed import fetch_articles, search_by_name, search_by_orcid
from core.target_author import identify_target_author
from core.feature_generator import compute_features
from core.scoring import score_articles
from core.config import load_config

logger = logging.getLogger(__name__)

# MAX_WORKERS module-level constant removed — now adaptive per run (D-12)

# Per-run cancel events. /api/pipeline/{run_id}/cancel sets the event;
# _process_one_researcher and run_pipeline check it between phases to stop
# in-flight and queued work without waiting for the executor to drain. See #13.
_CANCEL_EVENTS: dict[int, threading.Event] = {}
_CANCEL_EVENTS_LOCK = threading.Lock()


def _register_cancel_event(run_id: int) -> threading.Event:
    event = threading.Event()
    with _CANCEL_EVENTS_LOCK:
        _CANCEL_EVENTS[run_id] = event
    return event


def _unregister_cancel_event(run_id: int) -> None:
    with _CANCEL_EVENTS_LOCK:
        _CANCEL_EVENTS.pop(run_id, None)


def signal_cancel(run_id: int) -> bool:
    """Signal in-flight cancel for a run. Returns True if a live event was set."""
    with _CANCEL_EVENTS_LOCK:
        event = _CANCEL_EVENTS.get(run_id)
    if event is None:
        return False
    event.set()
    return True


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
        pmid=int(db_article.pmid) if db_article.pmid else 0,
        title=db_article.title or "",
        journal_title=db_article.journal or "",
        pub_year=db_article.pub_year or 0,
        authors=authors,
        doi=db_article.doi or "",
        abstract=db_article.abstract_text or "",
        mesh_headings=[
            MeshHeading(
                descriptor_name=m.get("descriptor_name", "") if isinstance(m, dict) else "",
                major_topic=m.get("major_topic", False) if isinstance(m, dict) else False,
            )
            for m in (db_article.mesh_headings or [])
        ],
        keywords=db_article.keywords or [],
        grants=db_article.grants or [],
        publication_types=db_article.publication_types or [],
    )


def _process_one_researcher(
    person_id: str,
    mode: str,
    config: dict,
    model_dir: str,
    run_id: int | None = None,
    cancel_event: threading.Event | None = None,
) -> dict:
    """
    Process a single researcher through the full pipeline.
    Runs in a thread. Returns a result dict.

    cancel_event is checked between phases. When set, the task short-circuits
    with {"cancelled": True} so PubMed quota and CPU are not spent on work the
    user has already abandoned.
    """
    def _cancelled() -> bool:
        return cancel_event is not None and cancel_event.is_set()

    if _cancelled():
        return {"person_id": person_id, "cancelled": True}

    db = SessionLocal()
    try:
        identity = db.query(Identity).filter_by(person_id=person_id).first()
        if not identity:
            return {"person_id": person_id, "error": "Identity not found"}

        core_identity = _db_identity_to_core(identity)
        from api.routers.institution import get_pubmed_api_key
        api_key = get_pubmed_api_key(db)

        # Phase 1: Retrieve articles
        if _cancelled():
            return {"person_id": person_id, "cancelled": True}
        person_articles = db.query(PersonArticle).filter_by(person_id=person_id).all()
        existing_pmids = {pa.pmid for pa in person_articles}

        if mode in ("full", "update"):
            # Check last retrieval date for incremental mode
            retrieval_log = db.query(RetrievalLog).filter_by(person_id=person_id).first()

            # For update mode, use last retrieval date as mindate filter
            mindate = ""
            if mode == "update" and retrieval_log and retrieval_log.last_retrieval_date:
                mindate = retrieval_log.last_retrieval_date.strftime("%Y/%m/%d")
                logger.info(f"{person_id}: incremental update since {mindate}")

            # Retrieval thresholds from config (matches ReCiter application.properties)
            retrieval_config = config.get("retrieval", {})
            lenient_threshold = retrieval_config.get("lenient_threshold", 3000)
            strict_threshold = retrieval_config.get("strict_threshold", 1500)

            search_result = search_by_name(
                first_name=core_identity.first_name,
                last_name=core_identity.last_name,
                api_key=api_key or "",
                lenient_threshold=lenient_threshold,
                strict_threshold=strict_threshold,
                mindate=mindate,
            )
            search_pmids = list(search_result["pmids"])
            query_type = search_result["query_type"]
            logger.info(
                f"{person_id}: retrieval strategy={query_type}, "
                f"lenient_count={search_result['lenient_count']}, "
                f"strict_count={search_result.get('strict_count')}, "
                f"pmids_returned={len(search_pmids)}"
            )

            # Mirrors upstream OrcidRetrievalStrategy (asserted ORCID source):
            # union ORCID-keyed PMIDs into the candidate set when available.
            # Catches articles where PubMed has a misspelled/transliterated name.
            if core_identity.orcid:
                orcid_result = search_by_orcid(
                    orcid=core_identity.orcid,
                    api_key=api_key or "",
                    mindate=mindate,
                )
                seen = {int(p) for p in search_pmids}
                added = [p for p in orcid_result["pmids"] if int(p) not in seen]
                search_pmids.extend(added)
                logger.info(
                    f"{person_id}: orcid retrieval count={orcid_result['count']}, "
                    f"added {len(added)} new pmids"
                )

            new_pmids = [p for p in search_pmids if str(p) not in existing_pmids]
            if new_pmids:
                articles = fetch_articles(new_pmids, api_key=api_key or "")

                # Build article rows for bulk upsert
                article_rows = []
                pa_rows = []
                for art in articles:
                    pmid_str = str(art.pmid)
                    article_rows.append(dict(
                        pmid=pmid_str,
                        title=art.title,
                        journal=art.journal_title,
                        pub_year=art.pub_year,
                        doi=art.doi,
                        abstract_text=art.abstract,
                        authors=[{
                            "first_name": a.first_name,
                            "last_name": a.last_name,
                            "initials": a.initials,
                            "affiliation": a.affiliation,
                            "orcid": getattr(a, "orcid", ""),
                        } for a in art.authors],
                        mesh_headings=[{"descriptor_name": m.descriptor_name, "major_topic": m.major_topic} for m in art.mesh_headings] if art.mesh_headings else [],
                        keywords=art.keywords or [],
                        grants=art.grants or [],
                        publication_types=art.publication_types or [],
                    ))
                    pa_rows.append(dict(
                        person_id=person_id, pmid=pmid_str, source="search",
                    ))

                # Upsert articles — no-op on duplicate (preserve existing article data)
                if article_rows:
                    stmt = mysql_insert(Article.__table__).values(article_rows)
                    db.execute(stmt.on_duplicate_key_update(pmid=stmt.inserted.pmid))

                # Upsert person-article links — no-op on duplicate
                if pa_rows:
                    stmt = mysql_insert(PersonArticle.__table__).values(pa_rows)
                    db.execute(stmt.on_duplicate_key_update(source=stmt.inserted.source))

            # Update retrieval log
            if retrieval_log:
                retrieval_log.articles_found = len(new_pmids)
                retrieval_log.run_id = run_id
            else:
                db.add(RetrievalLog(
                    person_id=person_id,
                    articles_found=len(new_pmids),
                    run_id=run_id,
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
        if _cancelled():
            return {"person_id": person_id, "cancelled": True}
        for art in core_articles:
            idx = identify_target_author(art, core_identity)
            art.target_author_index = idx
            # Update DB
            pa = db.query(PersonArticle).filter_by(
                person_id=person_id, pmid=str(art.pmid)
            ).first()
            if pa:
                pa.target_author_index = idx
        db.commit()

        # Phase 3: Feature generation
        if _cancelled():
            return {"person_id": person_id, "cancelled": True}
        curations = db.query(Curation).filter_by(person_id=person_id).all()
        has_curations = len(curations) > 0
        curation_map = {c.pmid: c.assertion for c in curations}

        # Set user_assertion on articles so feedback features work
        for art in core_articles:
            art.user_assertion = curation_map.get(str(art.pmid), "")

        feature_rows = compute_features(
            identity=core_identity,
            articles=core_articles,
            config=config,
        )

        if not feature_rows:
            return {
                "person_id": person_id,
                "article_count": len(core_articles),
                "scored_count": 0,
            }

        # Phase 4: Scoring
        if _cancelled():
            return {"person_id": person_id, "cancelled": True}
        curated_dict = {c.pmid: c.assertion for c in curations} if has_curations else {}
        scored_df = score_articles(
            feature_rows,
            curated=curated_dict,
            model_dir=os.path.basename(model_dir),
            identity_first_name=core_identity.first_name,
        )
        model_type = "feedbackIdentity" if has_curations else "identityOnly"

        # Build score rows for bulk upsert
        score_rows = []
        for _, row in scored_df.iterrows():
            pmid = str(row["pmid"])
            score_val = float(row.get("calibrated_score", 0))
            shap = row.get("shap_values")
            features_dict = {"shap": dict(shap)} if isinstance(shap, dict) else {}
            score_rows.append(dict(
                person_id=person_id,
                pmid=pmid,
                model_type=model_type,
                calibrated_score=score_val,
                raw_score=float(row.get("raw_score", 0)),
                features=features_dict,
                run_id=run_id,
            ))

        # Upsert scores — update all score fields on duplicate
        if score_rows:
            stmt = mysql_insert(PersonArticleScore.__table__).values(score_rows)
            db.execute(stmt.on_duplicate_key_update(
                calibrated_score=stmt.inserted.calibrated_score,
                raw_score=stmt.inserted.raw_score,
                features=stmt.inserted.features,
                run_id=stmt.inserted.run_id,
                scored_at=text('NOW()'),
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
    run_id: int | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Run the scoring pipeline for multiple researchers concurrently.
    Yields progress events as dicts in completion order (fastest researcher first).
    mode: "full" (retrieve + score), "update" (incremental), or "score_only"
    run_id: optional PipelineRun row PK for tagging scores and retrieval logs
    """
    config = load_config()

    # Merge institution config from DB into YAML config
    db = SessionLocal()
    try:
        from api.models import Institution as InstitutionModel
        import json as _json
        db_config = db.query(InstitutionModel).all()
        for row in db_config:
            key = row.config_key
            try:
                val = _json.loads(row.config_value)
            except (ValueError, TypeError):
                val = row.config_value
            if key == "email_suffixes":
                config.setdefault("institution", {})["email_suffixes"] = val
            elif key == "home_institution_keywords":
                config.setdefault("institution", {})["home_institution_keywords"] = val
            elif key == "collaborating_institution_keywords":
                config.setdefault("institution", {})["collaborating_keywords"] = val
            elif key == "institution_label":
                config.setdefault("institution", {})["institution_label"] = val
            elif key == "lenient_threshold" and isinstance(val, int):
                config.setdefault("retrieval", {})["lenient_threshold"] = val
            elif key == "strict_threshold" and isinstance(val, int):
                config.setdefault("retrieval", {})["strict_threshold"] = val
    finally:
        db.close()

    # Determine worker count from API key presence (per D-12)
    db_for_key = SessionLocal()
    try:
        from api.routers.institution import get_pubmed_api_key
        api_key = get_pubmed_api_key(db_for_key)
    finally:
        db_for_key.close()

    max_workers = 8 if api_key else 3

    model_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "models", "wcm",
    )

    total = len(person_ids)
    completed = 0

    # Per-run cancel event — set by /api/pipeline/{run_id}/cancel; checked
    # by each _process_one_researcher between phases. Registered only when
    # run_id is known so the cancel endpoint can find it.
    cancel_event: threading.Event | None = None
    if run_id is not None:
        cancel_event = _register_cancel_event(run_id)

    yield {
        "type": "started",
        "total": total,
        "mode": mode,
        "run_id": run_id,
        "max_workers": max_workers,
    }

    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=max_workers)

    try:
        # Submit all tasks
        futures = {}
        for pid in person_ids:
            future = loop.run_in_executor(
                executor, _process_one_researcher,
                pid, mode, config, model_dir, run_id, cancel_event,
            )
            futures[pid] = future
            yield {
                "type": "queued",
                "person_id": pid,
            }

        # Collect results in completion order (per D-11)
        # processing event removed per D-13
        all_futures = list(futures.values())
        for coro in _as_completed(all_futures):
            result = await coro
            pid = result["person_id"]  # already in result dict
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
            "run_id": run_id,
        }
    finally:
        if run_id is not None:
            _unregister_cancel_event(run_id)
