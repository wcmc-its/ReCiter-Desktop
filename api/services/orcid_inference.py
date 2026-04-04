"""
orcid_inference.py — Infer ORCID for researchers from target author position.

Looks at articles where the target author has an ORCID in PubMed.
If the same ORCID appears consistently across accepted/high-scoring articles,
it likely belongs to the researcher.

Confidence tiers:
  - confirmed: >=5 high-confidence articles, 0 rejected, sole ORCID
  - likely: 2-4 high-confidence articles, 0 rejected
  - possible: 1 high-confidence article, 0 rejected
  - unreliable: only in rejected/low-score articles, or competing ORCIDs
"""
import math
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy.orm import Session

from api.models import Identity, Article, PersonArticle, PersonArticleScore


def _wilson_lower_bound(successes: int, failures: int, z: float = 1.96) -> float:
    n = successes + failures
    if n == 0:
        return 0.0
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return (centre - spread) / denom


def _compute_confidence(
    accepted: int, rejected: int, n_distinct: int
) -> tuple[float, str]:
    volume = _wilson_lower_bound(accepted, rejected)
    uniqueness = 1.0 if n_distinct <= 1 else 1.0 / math.sqrt(n_distinct)
    score = round(volume * uniqueness, 4)

    if accepted >= 5 and rejected == 0 and n_distinct == 1:
        tier = "confirmed"
    elif accepted >= 2 and rejected == 0:
        tier = "likely"
    elif accepted >= 1 and rejected == 0:
        tier = "possible"
    else:
        tier = "unreliable"

    return score, tier


def infer_orcids(db: Session, score_threshold: float = 0.95) -> list[dict[str, Any]]:
    """
    Infer ORCIDs for all researchers based on target author position.

    For each researcher:
    1. Get their scored articles
    2. Find which author position was identified as the target
    3. Check if that author has an ORCID in PubMed data
    4. Aggregate across articles to compute confidence

    Args:
        db: Database session
        score_threshold: Score above which an article counts as "accepted"
                        (for institutions without curation data)

    Returns:
        List of dicts with person_id, orcid, confidence, tier, article counts
    """
    identities = db.query(Identity).all()
    results = []

    for identity in identities:
        person_id = identity.person_id

        # Get scored articles with their data
        scored = (
            db.query(PersonArticle, Article, PersonArticleScore)
            .join(Article, PersonArticle.pmid == Article.pmid)
            .join(
                PersonArticleScore,
                (PersonArticle.person_id == PersonArticleScore.person_id)
                & (PersonArticle.pmid == PersonArticleScore.pmid),
            )
            .filter(PersonArticle.person_id == person_id)
            .all()
        )

        if not scored:
            continue

        # Collect ORCIDs from target author position
        orcid_evidence: dict[str, dict] = defaultdict(
            lambda: {"accepted": 0, "rejected": 0, "pmids": []}
        )

        for pa, article, score in scored:
            target_idx = pa.target_author_index
            if target_idx < 0 or not article.authors:
                continue

            authors = article.authors
            if target_idx >= len(authors):
                continue

            target_author = authors[target_idx]
            orcid = (target_author.get("orcid") or "").strip()
            if not orcid:
                continue

            # Normalize ORCID
            orcid = (
                orcid.replace("https://orcid.org/", "")
                .replace("http://orcid.org/", "")
                .strip()
            )
            if not orcid or len(orcid) < 10:
                continue

            cal_score = score.calibrated_score or 0
            if cal_score >= score_threshold:
                orcid_evidence[orcid]["accepted"] += 1
            else:
                orcid_evidence[orcid]["rejected"] += 1
            orcid_evidence[orcid]["pmids"].append(article.pmid)

        if not orcid_evidence:
            continue

        n_distinct = len(orcid_evidence)
        for orcid, data in orcid_evidence.items():
            conf_score, tier = _compute_confidence(
                data["accepted"], data["rejected"], n_distinct
            )
            results.append({
                "person_id": person_id,
                "first_name": identity.first_name,
                "last_name": identity.last_name,
                "orcid": orcid,
                "confidence_score": conf_score,
                "confidence_tier": tier,
                "accepted_articles": data["accepted"],
                "rejected_articles": data["rejected"],
                "total_articles": data["accepted"] + data["rejected"],
                "identity_orcid": identity.orcid or "",
                "orcid_matches_identity": (
                    identity.orcid and orcid == identity.orcid.replace("https://orcid.org/", "").replace("http://orcid.org/", "").strip()
                ),
            })

    # Sort by confidence score descending
    results.sort(key=lambda x: (-x["confidence_score"], x["person_id"]))
    return results
