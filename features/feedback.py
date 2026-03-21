"""
feedback.py — Feedback score computation for all 12 dimensions.

Implements the sigmoid-based feedback scoring from
AbstractTargetAuthorFeedbackStrategy.java, including informed absence penalty.

Each dimension compares features of candidate articles against
previously accepted/rejected articles for the same person.
"""

import math
import logging
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

from core.article import Article
from core.identity import Identity
from features.journal_subfield import get_journal_subfield

_log = logging.getLogger(__name__)


# ── Core feedback formulas ───────────────────────────────────────────────────

def sigmoid_score(count_accepted: int, count_rejected: int) -> float:
    """
    Core sigmoid feedback formula.

    sigmoid = 1 / (1 + exp(-(accepted - rejected) / (sqrt(accepted + rejected) + 1))) - 0.5
    Range: [-0.5, 0.5]
    """
    diff = count_accepted - count_rejected
    total = count_accepted + count_rejected
    if total == 0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-diff / (math.sqrt(total) + 1))) - 0.5


def informed_absence_penalty(
    total_accepted: int,
    strength: float,
    scale: float = 10.0,
) -> float:
    """
    Penalty when a feature has never been seen but researcher has acceptance history.

    Returns a negative value.
    """
    if total_accepted <= 0 or strength <= 0:
        return 0.0
    sigmoid_val = 1.0 / (1.0 + math.exp(-total_accepted / scale))
    return -strength * (sigmoid_val - 0.5)


def determine_feedback_score(
    article_assertion: str,
    count_accepted: int,
    count_rejected: int,
) -> float:
    """
    Compute the leave-one-out feedback score.

    If the article being scored is itself ACCEPTED, exclude it from accepted count.
    If REJECTED, exclude from rejected count.
    If unasserted, use full counts.
    """
    if article_assertion == "ACCEPTED" and count_accepted > 0:
        return sigmoid_score(count_accepted - 1, count_rejected)
    elif article_assertion == "REJECTED" and count_rejected > 0:
        return sigmoid_score(count_accepted, count_rejected - 1)
    else:
        return sigmoid_score(count_accepted, count_rejected)


# ── Feature extraction helpers ───────────────────────────────────────────────

def _extract_target_author_name(article: Article) -> str:
    """Extract target author name for feedback matching."""
    ta = article.target_author
    if ta is None:
        return ""
    first = (ta.first_name or "").strip()
    last = (ta.last_name or "").strip()
    if first and last:
        return f"{first} {last}".lower()
    return ""


def _extract_coauthor_names(article: Article) -> List[str]:
    """Extract verbose (len > 1) non-target-author names."""
    names = []
    for a in article.non_target_authors:
        first = (a.first_name or "").strip()
        last = (a.last_name or "").strip()
        if len(first) > 1 and last:
            names.append(f"{first} {last}".lower())
    return names


def _extract_email_domain(article: Article) -> str:
    """Extract email domain from target author affiliation."""
    ta = article.target_author
    if ta is None or not ta.affiliation:
        return ""
    # Look for email pattern in affiliation
    aff = ta.affiliation.lower()
    import re
    match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', aff)
    if match:
        return match.group().split("@")[1]
    return ""


def _extract_institution(article: Article) -> str:
    """Extract institution from target author affiliation."""
    ta = article.target_author
    if ta is None:
        return ""
    return (ta.affiliation or "").lower()


def _extract_organization(article: Article, identity: Identity) -> str:
    """Extract organizational unit from target author affiliation."""
    ta = article.target_author
    if ta is None or not ta.affiliation:
        return ""
    if identity.department:
        dept_lower = identity.department.lower()
        if dept_lower in ta.affiliation.lower():
            return dept_lower
    return ""


def _extract_orcid(article: Article) -> str:
    """Extract target author ORCID."""
    ta = article.target_author
    if ta is None:
        return ""
    return (ta.orcid or "").strip()


def _extract_coauthor_orcids(article: Article) -> List[str]:
    """Extract non-target-author ORCIDs."""
    orcids = []
    for a in article.non_target_authors:
        if a.orcid:
            orcids.append(a.orcid.strip())
    return orcids


# ── Main feedback computation ────────────────────────────────────────────────

def compute_all_feedback_scores(
    article: Article,
    all_articles: List[Article],
    identity: Identity,
    config: dict,
) -> Dict[str, float]:
    """
    Compute all 12 feedback scores for a single article.

    Args:
        article: The article to score.
        all_articles: All articles for this person (including curated ones).
        identity: The researcher identity.
        config: Full config dict.

    Returns:
        Dict with all 12 feedbackScore* keys.
    """
    fb_cfg = config.get("feedback", {})
    ia_cfg = fb_cfg.get("informed_absence", {})
    ia_enabled = ia_cfg.get("enabled", True)
    ia_scale = ia_cfg.get("scale", 10.0)
    ia_strengths = ia_cfg.get("strength", {})

    # Count total accepted/rejected
    total_accepted = sum(1 for a in all_articles if a.user_assertion == "ACCEPTED")

    scores = {}

    # 1. Target Author Name
    scores["feedbackScoreTargetAuthorName"] = _compute_dimension_score(
        article=article,
        all_articles=all_articles,
        extract_fn=_extract_target_author_name,
        ia_strength=ia_strengths.get("targetAuthorName", 1.0) if ia_enabled else 0,
        ia_scale=ia_scale,
        total_accepted=total_accepted,
    )

    # 2. Co-Author Name (normalized by author count)
    scores["feedbackScoreCoAuthorName"] = _compute_multi_dimension_score(
        article=article,
        all_articles=all_articles,
        extract_fn=_extract_coauthor_names,
        normalize_by_count=True,
        ia_strength=ia_strengths.get("coAuthorName", 0.9) if ia_enabled else 0,
        ia_scale=ia_scale,
        total_accepted=total_accepted,
    )

    # 3. Email
    scores["feedbackScoreEmail"] = _compute_dimension_score(
        article=article,
        all_articles=all_articles,
        extract_fn=_extract_email_domain,
        ia_strength=ia_strengths.get("email", 0.3) if ia_enabled else 0,
        ia_scale=ia_scale,
        total_accepted=total_accepted,
    )

    # 4. Journal
    scores["feedbackScoreJournal"] = _compute_dimension_score(
        article=article,
        all_articles=all_articles,
        extract_fn=lambda a: (a.journal_title or "").lower(),
        ia_strength=ia_strengths.get("journal", 0.7) if ia_enabled else 0,
        ia_scale=ia_scale,
        total_accepted=total_accepted,
    )

    # 5. Journal SubField
    scores["feedbackScoreJournalSubField"] = _compute_dimension_score(
        article=article,
        all_articles=all_articles,
        extract_fn=lambda a: get_journal_subfield(a).lower(),
        ia_strength=ia_strengths.get("journalSubField", 0.7) if ia_enabled else 0,
        ia_scale=ia_scale,
        total_accepted=total_accepted,
    )

    # 6. Keyword (MeSH major topics, with rarity factor)
    scores["feedbackScoreKeyword"] = _compute_keyword_score(
        article=article,
        all_articles=all_articles,
        config=config,
        ia_strength=ia_strengths.get("keyword", 0.9) if ia_enabled else 0,
        ia_scale=ia_scale,
        total_accepted=total_accepted,
    )

    # 7. Institution
    scores["feedbackScoreInstitution"] = _compute_dimension_score(
        article=article,
        all_articles=all_articles,
        extract_fn=_extract_institution,
        ia_strength=ia_strengths.get("institution", 0.5) if ia_enabled else 0,
        ia_scale=ia_scale,
        total_accepted=total_accepted,
    )

    # 8. Organization
    scores["feedbackScoreOrganization"] = _compute_dimension_score(
        article=article,
        all_articles=all_articles,
        extract_fn=lambda a: _extract_organization(a, identity),
        ia_strength=ia_strengths.get("organization", 0.5) if ia_enabled else 0,
        ia_scale=ia_scale,
        total_accepted=total_accepted,
    )

    # 9. ORCID
    scores["feedbackScoreOrcid"] = _compute_dimension_score(
        article=article,
        all_articles=all_articles,
        extract_fn=_extract_orcid,
        ia_strength=ia_strengths.get("orcid", 0.3) if ia_enabled else 0,
        ia_scale=ia_scale,
        total_accepted=total_accepted,
    )

    # 10. ORCID Co-Author
    scores["feedbackScoreOrcidCoAuthor"] = _compute_multi_dimension_score(
        article=article,
        all_articles=all_articles,
        extract_fn=_extract_coauthor_orcids,
        normalize_by_count=False,
        ia_strength=0,  # Rarely useful
        ia_scale=ia_scale,
        total_accepted=total_accepted,
    )

    # 11. Cites (using DOI as proxy for citation matching)
    scores["feedbackScoreCites"] = _compute_dimension_score(
        article=article,
        all_articles=all_articles,
        extract_fn=lambda a: (a.doi or "").lower(),
        ia_strength=ia_strengths.get("cites", 0.5) if ia_enabled else 0,
        ia_scale=ia_scale,
        total_accepted=total_accepted,
    )

    # 12. Year
    scores["feedbackScoreYear"] = _compute_dimension_score(
        article=article,
        all_articles=all_articles,
        extract_fn=lambda a: str(a.pub_year) if a.pub_year else "",
        ia_strength=0,  # Year absence not meaningful
        ia_scale=ia_scale,
        total_accepted=total_accepted,
    )

    return scores


def _compute_dimension_score(
    article: Article,
    all_articles: List[Article],
    extract_fn,
    ia_strength: float,
    ia_scale: float,
    total_accepted: int,
) -> float:
    """Compute feedback score for a single-value dimension."""
    value = extract_fn(article)
    if not value:
        return 0.0

    # Count accepted/rejected articles with same feature value
    count_accepted = 0
    count_rejected = 0
    for a in all_articles:
        if a.pmid == article.pmid:
            continue
        a_value = extract_fn(a)
        if a_value == value:
            if a.user_assertion == "ACCEPTED":
                count_accepted += 1
            elif a.user_assertion == "REJECTED":
                count_rejected += 1

    if count_accepted > 0 or count_rejected > 0:
        return determine_feedback_score(
            article.user_assertion, count_accepted, count_rejected
        )

    # Informed absence
    if ia_strength > 0 and total_accepted > 0:
        return informed_absence_penalty(total_accepted, ia_strength, ia_scale)

    return 0.0


def _compute_multi_dimension_score(
    article: Article,
    all_articles: List[Article],
    extract_fn,
    normalize_by_count: bool,
    ia_strength: float,
    ia_scale: float,
    total_accepted: int,
) -> float:
    """Compute feedback score for a multi-value dimension (e.g., co-authors)."""
    values = extract_fn(article)
    if not values:
        return 0.0

    total_score = 0.0
    matched_any = False

    for value in values:
        if not value:
            continue

        count_accepted = 0
        count_rejected = 0
        for a in all_articles:
            if a.pmid == article.pmid:
                continue
            a_values = extract_fn(a)
            if value in a_values:
                if a.user_assertion == "ACCEPTED":
                    count_accepted += 1
                elif a.user_assertion == "REJECTED":
                    count_rejected += 1

        if count_accepted > 0 or count_rejected > 0:
            matched_any = True
            item_score = determine_feedback_score(
                article.user_assertion, count_accepted, count_rejected
            )
            total_score += item_score

    if normalize_by_count and len(values) > 0:
        total_score /= len(values)

    if not matched_any and ia_strength > 0 and total_accepted > 0:
        return informed_absence_penalty(total_accepted, ia_strength, ia_scale)

    return total_score


def _compute_keyword_score(
    article: Article,
    all_articles: List[Article],
    config: dict,
    ia_strength: float,
    ia_scale: float,
    total_accepted: int,
) -> float:
    """Compute feedbackScoreKeyword with rarity factor for MeSH terms."""
    fb_cfg = config.get("feedback", {})
    keyword_baseline = fb_cfg.get("keyword_count_baseline", 1319351)
    keyword_log_base = fb_cfg.get("keyword_log_base", 25)
    keyword_offset = fb_cfg.get("keyword_offset", 0.4)

    # Extract major MeSH terms
    terms = article.major_mesh_terms
    if not terms:
        terms = article.keywords

    if not terms:
        return 0.0

    total_score = 0.0
    matched_any = False

    for term in terms:
        term_lower = term.lower()
        if not term_lower:
            continue

        count_accepted = 0
        count_rejected = 0
        for a in all_articles:
            if a.pmid == article.pmid:
                continue
            a_terms = [t.lower() for t in (a.major_mesh_terms or a.keywords)]
            if term_lower in a_terms:
                if a.user_assertion == "ACCEPTED":
                    count_accepted += 1
                elif a.user_assertion == "REJECTED":
                    count_rejected += 1

        if count_accepted > 0 or count_rejected > 0:
            matched_any = True
            item_score = determine_feedback_score(
                article.user_assertion, count_accepted, count_rejected
            )
            # Rarity factor: rare terms get higher weight
            # For v1, use a simplified version (no global MeSH count available)
            total_score += item_score

    if not matched_any and ia_strength > 0 and total_accepted > 0:
        return informed_absence_penalty(total_accepted, ia_strength, ia_scale)

    return total_score
