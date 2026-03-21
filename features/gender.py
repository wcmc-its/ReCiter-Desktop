"""
gender.py — Gender evidence scoring.

Produces genderScoreIdentityArticleDiscrepancy by comparing
gender probabilities for identity and article author first names.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

from core.article import Article
from core.identity import Identity

_log = logging.getLogger(__name__)

_GENDER_TABLE: Optional[Dict[str, Tuple[str, float]]] = None


def _load_gender_table():
    """Load Gender.json: name → (gender, probability)."""
    global _GENDER_TABLE
    if _GENDER_TABLE is not None:
        return

    gender_path = Path(__file__).parent.parent / "data" / "gender" / "Gender.json"
    _GENDER_TABLE = {}
    if gender_path.exists():
        with open(gender_path, "r") as f:
            entries = json.load(f)
        for entry in entries:
            name = entry.get("name", "").lower()
            gender = entry.get("gender", "")
            prob = float(entry.get("probability", 0))
            if name:
                _GENDER_TABLE[name] = (gender, prob)
        _log.info(f"Loaded gender table: {len(_GENDER_TABLE)} names")


def _lookup_gender(first_name: str) -> Optional[Tuple[str, float]]:
    """Look up gender and probability for a first name."""
    _load_gender_table()
    if not first_name:
        return None
    name = first_name.strip().lower().split()[0] if first_name else ""
    return _GENDER_TABLE.get(name)


def compute_gender_score(
    article: Article,
    identity: Identity,
    config: dict,
) -> float:
    """
    Compute genderScoreIdentityArticleDiscrepancy.

    Compares gender probability for identity first name vs article
    target author first name. Returns score in [minimum_score, minimum_score + range_score].
    """
    gender_cfg = config.get("gender", {})
    min_score = gender_cfg.get("minimum_score", -1.36)
    range_score = gender_cfg.get("range_score", 1.6)

    target = article.target_author
    if target is None:
        return 0.0

    id_gender = _lookup_gender(identity.first_name)
    art_gender = _lookup_gender(target.first_name)

    if id_gender is None or art_gender is None:
        return 0.0

    id_g, id_prob = id_gender
    art_g, art_prob = art_gender

    # Same gender → positive score proportional to confidence
    # Different gender → negative score proportional to confidence
    if id_g == art_g:
        # Both same gender: higher confidence → higher score
        confidence = min(id_prob, art_prob)
        return min_score + range_score * confidence
    else:
        # Different genders: higher confidence → more negative
        confidence = min(id_prob, art_prob)
        return min_score + range_score * (1 - confidence)
