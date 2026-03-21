"""
feature_generator.py — Orchestrates computation of all 32 base features for each article.

Ties together target author selection + all feature modules.
"""

import logging
from typing import Dict, List

from core.article import Article
from core.identity import Identity
from core.target_author import identify_target_author
from features.name_match import compute_name_scores
from features.email_match import compute_email_score
from features.affiliation import compute_affiliation_scores
from features.organization import compute_organization_score
from features.journal_subfield import compute_journal_subfield_score
from features.degree_year import compute_degree_year_score
from features.gender import compute_gender_score
from features.article_size import compute_article_count_score
from features.author_count import compute_author_count_score
from features.feedback import compute_all_feedback_scores

_log = logging.getLogger(__name__)


def compute_features(
    identity: Identity,
    articles: List[Article],
    config: dict,
) -> List[Dict]:
    """
    Compute all base features for a list of articles.

    Steps:
    1. Run target author selection for each article
    2. Compute 18 identity features per article
    3. Compute 12 feedback features per article (if curated articles exist)
    4. Add countAccepted / countRejected

    Args:
        identity: Researcher identity
        articles: All candidate articles for this person (including curated ones)
        config: Full config dict

    Returns:
        List of feature dicts, one per article, each with pmid + all feature values.
    """
    if not articles:
        return []

    # Step 1: Target author selection
    for article in articles:
        idx = identify_target_author(article, identity)
        article.target_author_index = idx
        if idx >= 0:
            article.authors[idx].is_target_author = True

    total_articles = len(articles)
    article_count_score = compute_article_count_score(total_articles, config)

    # Count curated articles
    count_accepted = sum(1 for a in articles if a.user_assertion == "ACCEPTED")
    count_rejected = sum(1 for a in articles if a.user_assertion == "REJECTED")
    has_feedback = count_accepted > 0 or count_rejected > 0

    feature_rows = []
    for article in articles:
        row = {"pmid": article.pmid}

        # ── Identity features ─────────────────────────────────────────
        name_scores = compute_name_scores(article, identity, config)
        row.update(name_scores)

        row["emailMatchScore"] = compute_email_score(article, identity, config)

        affil_scores = compute_affiliation_scores(article, identity, config)
        row.update(affil_scores)

        row["organizationalUnitMatchingScore"] = compute_organization_score(
            article, identity, config
        )

        row["journalSubfieldScore"] = compute_journal_subfield_score(
            article, identity, config
        )

        row["discrepancyDegreeYearScore"] = compute_degree_year_score(
            article, identity, config
        )

        row["genderScoreIdentityArticleDiscrepancy"] = compute_gender_score(
            article, identity, config
        )

        row["articleCountScore"] = article_count_score
        row["authorCountScore"] = compute_author_count_score(article, config)

        # Features defaulting to 0 in v1
        row["grantMatchScore"] = 0.0
        row["relationshipPositiveMatchScore"] = 0.0
        row["relationshipNegativeMatchScore"] = 0.0
        row["relationshipIdentityCount"] = 0.0

        # ── Feedback features ─────────────────────────────────────────
        if has_feedback:
            feedback_scores = compute_all_feedback_scores(
                article, articles, identity, config
            )
            row.update(feedback_scores)
            row["countAccepted"] = count_accepted
            row["countRejected"] = count_rejected
        else:
            # Zero out feedback features for identity-only model
            for key in [
                "feedbackScoreCites", "feedbackScoreCoAuthorName",
                "feedbackScoreEmail", "feedbackScoreInstitution",
                "feedbackScoreJournal", "feedbackScoreJournalSubField",
                "feedbackScoreKeyword", "feedbackScoreOrcid",
                "feedbackScoreOrcidCoAuthor", "feedbackScoreOrganization",
                "feedbackScoreTargetAuthorName", "feedbackScoreYear",
            ]:
                row[key] = 0.0
            row["countAccepted"] = 0
            row["countRejected"] = 0

        # Add identity first name for name frequency scoring
        row["identityFirstName"] = identity.first_name

        feature_rows.append(row)

    return feature_rows
