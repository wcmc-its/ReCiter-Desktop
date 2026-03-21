"""
affiliation.py — Institutional affiliation matching.

Produces:
  - pubmedTargetAuthorInstitutionalAffiliationMatchTypeScore
  - targetAuthorInstitutionalAffiliationMatchTypeScore
  - scopusNonTargetAuthorInstitutionalAffiliationScore (always 0 — no Scopus)
"""

from typing import Dict, List

from core.article import Article
from core.identity import Identity


def _tokenize(text: str, stopwords: List[str]) -> List[str]:
    """Lowercase and remove stopwords."""
    words = text.lower().split()
    return [w for w in words if w not in stopwords]


def _check_keyword_groups(affiliation: str, keyword_groups: List[List[str]]) -> bool:
    """Check if ANY keyword group has ALL its keywords present in the affiliation."""
    aff_lower = affiliation.lower()
    for group in keyword_groups:
        if all(kw.lower() in aff_lower for kw in group):
            return True
    return False


def compute_affiliation_scores(
    article: Article,
    identity: Identity,
    config: dict,
) -> Dict[str, float]:
    """
    Compute affiliation-based scores for an article.

    Returns dict with:
        pubmedTargetAuthorInstitutionalAffiliationMatchTypeScore
        targetAuthorInstitutionalAffiliationMatchTypeScore
        scopusNonTargetAuthorInstitutionalAffiliationScore
    """
    affil_cfg = config.get("affiliation", {})
    ta_cfg = affil_cfg.get("target_author", {})
    inst_cfg = config.get("institution", {})

    home_keywords = inst_cfg.get("home_institution_keywords", [])
    email_suffixes = inst_cfg.get("email_suffixes", [])

    # Parse keyword groups from config
    # Each entry can be a list of keywords, or a pipe-delimited string
    keyword_groups = []
    for entry in home_keywords:
        if isinstance(entry, str):
            # Parse pipe-delimited format: "weil|cornell"
            keyword_groups.append([kw.strip() for kw in entry.split("|")])
        elif isinstance(entry, list):
            keyword_groups.append(entry)

    target = article.target_author
    pubmed_score = ta_cfg.get("null_score", 0.0)

    if target is not None and target.affiliation:
        aff = target.affiliation

        # Check if email suffix appears in affiliation
        email_match = False
        for suffix in email_suffixes:
            if suffix.lower().lstrip("@") in aff.lower():
                email_match = True
                break

        # Check keyword groups
        keyword_match = _check_keyword_groups(aff, keyword_groups)

        # Check identity institution
        inst_match = False
        if identity.primary_institution:
            inst_words = identity.primary_institution.lower().split()
            if len(inst_words) >= 2:
                inst_match = all(w in aff.lower() for w in inst_words if len(w) > 2)
            elif inst_words:
                inst_match = inst_words[0] in aff.lower()

        if email_match or keyword_match:
            pubmed_score = ta_cfg.get("positive_match_individual", 1.8)
        elif inst_match:
            pubmed_score = ta_cfg.get("positive_match_institution", 1.0)
        else:
            pubmed_score = ta_cfg.get("no_match", -0.8)
    elif target is not None and not target.affiliation:
        pubmed_score = ta_cfg.get("null_score", 0.0)

    # targetAuthorInstitutionalAffiliationMatchTypeScore:
    # In Java, this combines PubMed + Scopus. Without Scopus, just use PubMed score.
    target_author_score = pubmed_score

    return {
        "pubmedTargetAuthorInstitutionalAffiliationMatchTypeScore": pubmed_score,
        "targetAuthorInstitutionalAffiliationMatchTypeScore": target_author_score,
        "scopusNonTargetAuthorInstitutionalAffiliationScore": 0.0,
    }
