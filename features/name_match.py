"""
name_match.py — Name matching feature computation.

Produces 4 scores: nameMatchFirstScore, nameMatchLastScore,
nameMatchMiddleScore, nameMatchModifierScore.

Reimplements ScoreByNameStrategy.java.
"""

import re
from typing import Dict, Tuple

from Levenshtein import distance as levenshtein_distance

from core.article import Article
from core.identity import Identity


def _normalize(s: str) -> str:
    return s.lower().replace(".", "").replace("-", " ").replace("'", "").strip()


def _strip_suffixes(name: str, suffixes: list) -> str:
    """Remove trailing suffixes like Jr, MD, PhD."""
    for suffix in suffixes:
        # Check for ", suffix" or " suffix" at end
        for pattern in [f", {suffix}", f" {suffix}"]:
            if name.lower().endswith(pattern.lower()):
                name = name[: -len(pattern)].strip()
    return name


def compute_name_scores(
    article: Article,
    identity: Identity,
    config: dict,
) -> Dict[str, float]:
    """
    Compute name match scores for an article against an identity.

    Returns dict with keys:
        nameMatchFirstScore, nameMatchLastScore,
        nameMatchMiddleScore, nameMatchModifierScore
    """
    ns = config.get("name_scoring", {})
    first_cfg = ns.get("first_name", {})
    last_cfg = ns.get("last_name", {})
    middle_cfg = ns.get("middle_name", {})
    modifier_cfg = ns.get("modifier", {})
    suffixes = ns.get("excluded_suffixes", [])

    target = article.target_author
    if target is None:
        return {
            "nameMatchFirstScore": first_cfg.get("nullTargetAuthor_MatchNotAttempted", -1.323),
            "nameMatchLastScore": last_cfg.get("nullTargetAuthor_MatchNotAttempted", -0.996),
            "nameMatchMiddleScore": middle_cfg.get("nullTargetAuthor_MatchNotAttempted", -1.588),
            "nameMatchModifierScore": 0.0,
        }

    # Normalize identity names
    id_first = _normalize(identity.first_name)
    id_last = _normalize(identity.last_name)
    id_middle = _normalize(identity.middle_name)

    # Normalize article target author names
    a_first_raw = _strip_suffixes(target.first_name or "", suffixes)
    a_last_raw = _strip_suffixes(target.last_name or "", suffixes)

    # Extract first and middle from ForeName
    fore_parts = a_first_raw.split()
    a_first = _normalize(fore_parts[0]) if fore_parts else ""
    a_middle = _normalize(" ".join(fore_parts[1:])) if len(fore_parts) > 1 else ""
    # Also check initials for middle
    if not a_middle and target.initials and len(target.initials) > 1:
        a_middle = target.initials[1:].lower()

    a_last = _normalize(a_last_raw)

    modifier_score = 0.0

    # ── First name score ──────────────────────────────────────────────────
    first_score = _score_first_name(id_first, a_first, first_cfg)

    # ── Last name score ───────────────────────────────────────────────────
    last_score = _score_last_name(id_last, a_last, last_cfg)

    # ── Middle name score ─────────────────────────────────────────────────
    middle_score = _score_middle_name(id_middle, a_middle, middle_cfg)

    # ── Modifier scores ───────────────────────────────────────────────────

    # Combined first+last name match (e.g., "Jean-Pierre Dupont" vs "JeanPierre Dupont")
    id_combined = re.sub(r"[\s\-]", "", id_first + id_last)
    a_combined = re.sub(r"[\s\-]", "", a_first + a_last)
    if id_combined and a_combined and id_combined == a_combined:
        modifier_score += modifier_cfg.get("combinedFirstNameLastName", 0.451)

    # Combined middle+last name
    if id_middle:
        id_mid_last = _normalize(identity.middle_name + identity.last_name)
        if a_last and id_mid_last == a_last:
            modifier_score += modifier_cfg.get("combinedMiddleNameLastName", 0)

    # Incorrect order (first/last swapped)
    if (len(id_first) > 1 and len(id_last) > 1
            and a_first == id_last and a_last == id_first):
        modifier_score += modifier_cfg.get("incorrectOrder", -0.804)

    # Identity substring of article (first name)
    if (len(id_first) > 1 and len(a_first) > len(id_first)
            and a_first.startswith(id_first)):
        modifier_score += modifier_cfg.get("identitySubstringOfArticle_firstName", -1.608)

    # Identity substring of article (last name)
    if (len(id_last) > 1 and len(a_last) > len(id_last)
            and id_last in a_last):
        modifier_score += modifier_cfg.get("identitySubstringOfArticle_lastName", -1.608)

    # Article substring of identity (last name)
    if (len(a_last) > 1 and len(id_last) > len(a_last)
            and a_last in id_last):
        modifier_score += modifier_cfg.get("articleSubstringOfIdentity_lastName", -0.804)

    # Identity first+middle substring of article first
    if id_middle and len(id_first) > 1:
        id_first_mid = _normalize(identity.first_name + identity.middle_name)
        if len(id_first_mid) > 1 and id_first_mid in a_first:
            modifier_score += modifier_cfg.get("identitySubstringOfArticle_firstMiddleName", 0.804)

    return {
        "nameMatchFirstScore": first_score,
        "nameMatchLastScore": last_score,
        "nameMatchMiddleScore": middle_score,
        "nameMatchModifierScore": modifier_score,
    }


def _score_first_name(id_first: str, a_first: str, cfg: dict) -> float:
    """Score first name match."""
    if not a_first or not id_first:
        return cfg.get("noMatch", -1.941)

    # Exact match
    if id_first == a_first:
        return cfg.get("full_exact", 1.852)

    # Initial match (article has initial only, or identity initial matches)
    if len(a_first) == 1:
        if a_first == id_first[0]:
            return cfg.get("inferredInitials_exact", 0.441)
        else:
            return cfg.get("full_conflictingEntirely", -3.087)

    if len(id_first) == 1:
        if id_first == a_first[0]:
            return cfg.get("inferredInitials_exact", 0.441)
        else:
            return cfg.get("full_conflictingEntirely", -3.087)

    # Fuzzy match (Levenshtein distance <= 1 for names >= 4 chars)
    if len(id_first) >= 4 and len(a_first) >= 4:
        dist = levenshtein_distance(id_first, a_first)
        if dist == 1:
            return cfg.get("full_fuzzy", -0.75)

    # First 3 chars match
    if len(id_first) >= 3 and len(a_first) >= 3 and id_first[:3] == a_first[:3]:
        return cfg.get("full_fuzzy", -0.75)

    # Same initial, different name
    if id_first[0] == a_first[0]:
        return cfg.get("full_conflictingAllButInitials", -2.646)

    # Entirely different
    return cfg.get("full_conflictingEntirely", -3.087)


def _score_last_name(id_last: str, a_last: str, cfg: dict) -> float:
    """Score last name match."""
    if not a_last or not id_last:
        return cfg.get("nullTargetAuthor_MatchNotAttempted", -0.996)

    if id_last == a_last:
        return cfg.get("full_exact", 0.664)

    # Fuzzy match
    if len(id_last) >= 4 and len(a_last) >= 4:
        dist = levenshtein_distance(id_last, a_last)
        if dist <= 1:
            return cfg.get("full_fuzzy", 0.332)

    return cfg.get("full_conflictingEntirely", -0.996)


def _score_middle_name(id_middle: str, a_middle: str, cfg: dict) -> float:
    """Score middle name match."""
    # Identity has no middle name
    if not id_middle:
        return cfg.get("identityNull_MatchNotAttempted", 0.794)

    # Article has no middle name
    if not a_middle:
        return cfg.get("noMatch", -0.794)

    # Exact match
    if id_middle == a_middle:
        if len(id_middle) == 1:
            return cfg.get("exact_singleInitial", 1.191)
        return cfg.get("full_exact", 1.588)

    # Initial match
    if len(a_middle) == 1 and a_middle == id_middle[0]:
        return cfg.get("inferredInitials_exact", 0.794)
    if len(id_middle) == 1 and id_middle == a_middle[0]:
        return cfg.get("inferredInitials_exact", 0.794)

    # Fuzzy match
    if len(id_middle) >= 4 and len(a_middle) >= 4:
        dist = levenshtein_distance(id_middle, a_middle)
        if dist <= 1:
            return cfg.get("full_fuzzy", 0)

    # Conflicting entirely
    return cfg.get("full_conflictingEntirely", -1.588)
