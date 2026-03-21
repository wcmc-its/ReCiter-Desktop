"""
journal_subfield.py — Journal subfield matching.

Produces journalSubfieldScore by mapping article's journal (via ISSN)
to ScienceMetrix subfield and comparing to researcher's department.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from core.article import Article
from core.identity import Identity

_log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data" / "science_metrix"

# Lazily loaded lookup tables
_issn_to_subfield: Optional[Dict[str, str]] = None
_dept_to_subfields: Optional[Dict[str, Set[str]]] = None


def _load_science_metrix():
    """Load ScienceMetrix journal→subfield and department→subfield mappings."""
    global _issn_to_subfield, _dept_to_subfields

    if _issn_to_subfield is not None:
        return

    _issn_to_subfield = {}
    _dept_to_subfields = {}

    # Load journal → subfield (from ScienceMetrix.json)
    sm_path = _DATA_DIR / "ScienceMetrix.json"
    if sm_path.exists():
        with open(sm_path, "r") as f:
            entries = json.load(f)
        for entry in entries:
            subfield = entry.get("scienceMetrixSubfield", "")
            for key in ["issn", "eissn"]:
                issn = entry.get(key, "")
                if issn and subfield:
                    _issn_to_subfield[issn.replace("-", "").lower()] = subfield
        _log.info(f"Loaded ScienceMetrix: {len(_issn_to_subfield)} ISSN→subfield mappings")

    # Load department → subfield (from ScienceMetrixDepartmentCategory.json)
    dc_path = _DATA_DIR / "ScienceMetrixDepartmentCategory.json"
    if dc_path.exists():
        with open(dc_path, "r") as f:
            entries = json.load(f)
        for entry in entries:
            dept = entry.get("primaryDepartment", "").lower()
            subfield = entry.get("scienceMetrixJournalSubfield", "")
            if dept and subfield:
                if dept not in _dept_to_subfields:
                    _dept_to_subfields[dept] = set()
                _dept_to_subfields[dept].add(subfield)
        _log.info(f"Loaded ScienceMetrix: {len(_dept_to_subfields)} department→subfield mappings")


def get_journal_subfield(article: Article) -> str:
    """Look up the ScienceMetrix subfield for an article's journal."""
    _load_science_metrix()
    for issn in article.journal_issn:
        normalized = issn.replace("-", "").lower()
        if normalized in _issn_to_subfield:
            return _issn_to_subfield[normalized]
    return ""


def compute_journal_subfield_score(
    article: Article,
    identity: Identity,
    config: dict,
) -> float:
    """
    Compute journalSubfieldScore.

    Maps article journal → ScienceMetrix subfield → compare to identity department.
    """
    _load_science_metrix()

    js_cfg = config.get("journal_subfield", {})
    factor_score = js_cfg.get("factor_score", 0.470)
    no_match_score = js_cfg.get("no_match_score", -0.470)

    if not identity.department:
        return 0.0

    subfield = get_journal_subfield(article)
    if not subfield:
        return 0.0

    # Check if identity's department maps to this journal's subfield
    dept_lower = identity.department.lower()

    # Direct department lookup
    if dept_lower in _dept_to_subfields:
        if subfield in _dept_to_subfields[dept_lower]:
            return factor_score

    # Also check org unit synonyms — try normalized department names
    inst_cfg = config.get("institution", {})
    synonyms = inst_cfg.get("org_unit_synonyms", {})
    for syn_key, syn_list in synonyms.items():
        all_names = [syn_key.lower()] + [s.lower() for s in syn_list]
        if dept_lower in all_names:
            for name in all_names:
                if name in _dept_to_subfields:
                    if subfield in _dept_to_subfields[name]:
                        return factor_score
            break

    return no_match_score
