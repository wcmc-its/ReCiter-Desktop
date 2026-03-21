"""
email_match.py — Email matching feature computation.

Produces emailMatchScore by checking if identity email appears
in target author's PubMed affiliation.
"""

from typing import Dict

from core.article import Article
from core.identity import Identity


def compute_email_score(
    article: Article,
    identity: Identity,
    config: dict,
) -> float:
    """
    Compute emailMatchScore for an article.

    Checks whether the identity's email (or email uid) appears in the
    target author's affiliation string.
    """
    email_cfg = config.get("email", {})
    match_score = email_cfg.get("match_score", 8.0)
    no_match_score = email_cfg.get("no_match_score", -1.0)

    if not identity.primary_email:
        return 0.0

    target = article.target_author
    if target is None:
        return 0.0

    affiliation = (target.affiliation or "").lower()
    if not affiliation:
        return 0.0

    email_lower = identity.primary_email.lower()
    email_uid = identity.email_uid
    email_domain = identity.email_domain

    # Check full email
    if email_lower in affiliation:
        return match_score

    # Check uid@domain pattern in affiliation
    if email_uid and email_uid in affiliation:
        return match_score

    # Also check configured institution email suffixes
    inst_suffixes = config.get("institution", {}).get("email_suffixes", [])
    for suffix in inst_suffixes:
        suffix_clean = suffix.lower().lstrip("@")
        if suffix_clean in affiliation:
            # Institution email domain appears, but not the specific user's email
            # Still a partial signal — but per Java, this gives no_match
            pass

    return no_match_score
