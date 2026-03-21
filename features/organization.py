"""
organization.py — Organizational unit matching.

Produces organizationalUnitMatchingScore.
"""

from typing import Dict, List

from core.article import Article
from core.identity import Identity


def compute_organization_score(
    article: Article,
    identity: Identity,
    config: dict,
) -> float:
    """
    Compute organizationalUnitMatchingScore.

    Checks if identity's department appears in target author's affiliation.
    Uses org_unit_synonyms from config for fuzzy matching.
    """
    org_cfg = config.get("organization", {})
    dept_score = org_cfg.get("department_match_score", 0.6)
    modifier_dept = org_cfg.get("modifier_department", "Medicine")
    modifier_score = org_cfg.get("modifier_score", 0.0)
    program_score = org_cfg.get("program_match_score", 1.083)

    if not identity.department:
        return 0.0

    target = article.target_author
    if target is None or not target.affiliation:
        return 0.0

    aff_lower = target.affiliation.lower()
    dept_lower = identity.department.lower()

    # Check if department is the common "Medicine" modifier
    if dept_lower == modifier_dept.lower():
        if modifier_dept.lower() in aff_lower:
            return modifier_score
        return 0.0

    # Get synonyms from config
    inst_cfg = config.get("institution", {})
    synonyms = inst_cfg.get("org_unit_synonyms", {})

    # Build list of names to check (department + synonyms)
    names_to_check = [dept_lower]
    for syn_key, syn_list in synonyms.items():
        all_names = [syn_key.lower()] + [s.lower() for s in syn_list]
        if dept_lower in all_names:
            names_to_check.extend(all_names)
            break

    # Check affiliation for any matching name
    for name in names_to_check:
        if name and name in aff_lower:
            return dept_score

    return 0.0
