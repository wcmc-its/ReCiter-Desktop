"""
article_size.py — Article count scoring.

Produces articleCountScore based on total candidate articles for a person.
Fewer candidates → higher prior probability for each article.
"""

import math

from core.article import Article
from core.identity import Identity


def compute_article_count_score(
    total_articles: int,
    config: dict,
) -> float:
    """
    Compute articleCountScore.

    Based on total candidate articles for this person.
    Formula: threshold/weight * (1 - totalArticles/threshold)
    Clamped so that having few articles gives a positive score
    and many articles gives a negative score.
    """
    ac_cfg = config.get("article_count", {})
    threshold = ac_cfg.get("threshold_score", 800)
    weight = ac_cfg.get("weight", 583.9)

    if total_articles <= 0:
        return 0.0

    # Score approaches 0 as articles approach threshold
    # Positive when below threshold, negative when above
    score = (threshold / weight) * (1.0 - total_articles / threshold)
    return score
