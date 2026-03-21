"""
author_count.py — Author count scoring.

Produces authorCountScore based on number of authors on an article.
More authors → harder to determine authorship → adjusted likelihood.
"""

import math

from core.article import Article


def compute_author_count_score(
    article: Article,
    config: dict,
) -> float:
    """
    Compute authorCountScore.

    Uses a log-based formula: ln_coefficient * ln(authorCount) + constant_coefficient
    adjusted by a gamma parameter relative to a median threshold.
    """
    ac_cfg = config.get("article_count", {})
    threshold = ac_cfg.get("author_count_threshold", 6)
    gamma = ac_cfg.get("author_count_adjustment_gamma", 2.6)
    ln_coeff = ac_cfg.get("ln_coefficient", -0.2461)
    const_coeff = ac_cfg.get("constant_coefficient", 1.98)

    n_authors = article.author_count
    if n_authors <= 0:
        return 0.0

    # Base likelihood from author count
    score = ln_coeff * math.log(max(n_authors, 1)) + const_coeff

    return score
