"""
degree_year.py — Education year discrepancy scoring.

Produces discrepancyDegreeYearScore based on the difference between
publication year and doctoral/bachelor year.
"""

from core.article import Article
from core.identity import Identity


def compute_degree_year_score(
    article: Article,
    identity: Identity,
    config: dict,
) -> float:
    """
    Compute discrepancyDegreeYearScore.

    Calculates pub_year - degree_year and looks up score from the
    200-entry table in config. Heavily penalizes articles published
    before the researcher's degree.
    """
    dy_cfg = config.get("degree_year", {})
    score_table = dy_cfg.get("score_table", {})
    bachelor_weight = dy_cfg.get("bachelor_year_weight", -7)

    # Determine effective degree year
    degree_year = 0
    if identity.doctoral_year and identity.doctoral_year > 0:
        degree_year = identity.doctoral_year
    elif identity.bachelor_year and identity.bachelor_year > 0:
        degree_year = identity.bachelor_year + bachelor_weight
    else:
        return 0.0

    if not article.pub_year or article.pub_year <= 0:
        return 0.0

    diff = article.pub_year - degree_year

    # Look up in score table (keys are ints)
    if diff in score_table:
        return score_table[diff]

    # Clamp to table bounds
    min_diff = min(score_table.keys()) if score_table else -99
    max_diff = max(score_table.keys()) if score_table else 100

    if diff < min_diff:
        return score_table.get(min_diff, -12.6)
    if diff > max_diff:
        return score_table.get(max_diff, -1.61)

    return 0.0
