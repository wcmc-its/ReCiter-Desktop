"""
target_author.py — Target author selection (19-step cascade).

Identifies which author on a PubMed article corresponds to the target researcher.
Reimplements TargetAuthorSelection.java steps 1-19.
"""

import logging
from typing import List, Optional, Tuple

from Levenshtein import distance as levenshtein_distance

from core.article import Article, Author
from core.identity import Identity

_log = logging.getLogger(__name__)


def _normalize(s: str) -> str:
    """Normalize a name string for comparison: lowercase, strip periods/spaces/dashes."""
    return s.lower().replace(".", "").replace("-", "").replace("'", "").strip()


def _first_initial(name: str) -> str:
    """Extract first character, lowered."""
    return name[0].lower() if name else ""


def identify_target_author(article: Article, identity: Identity) -> int:
    """
    Run the 19-step cascade to identify the target author on an article.

    Returns the 0-based index of the matched author, or -1 if no match found.
    """
    authors = article.authors
    if not authors:
        return -1

    id_first = _normalize(identity.first_name)
    id_last = _normalize(identity.last_name)
    id_middle = _normalize(identity.middle_name)
    id_first_init = _first_initial(identity.first_name)
    id_middle_init = _first_initial(identity.middle_name)

    # Step 1: Exact last + middle + first
    if id_middle:
        matches = []
        for i, a in enumerate(authors):
            a_first = _normalize(a.first_name)
            a_last = _normalize(a.last_name)
            # Extract middle from initials if available
            a_middle = ""
            if a.initials and len(a.initials) > 1:
                # PubMed initials are like "RJ" for Robert J — second char is middle initial
                pass
            # Try matching ForeName parts for middle name
            fore_parts = (a.first_name or "").split()
            if len(fore_parts) > 1:
                a_middle = _normalize(" ".join(fore_parts[1:]))
                a_first = _normalize(fore_parts[0])

            if a_last == id_last and a_first == id_first and a_middle == id_middle:
                matches.append(i)
        if len(matches) == 1:
            return matches[0]

    # Step 2: Exact last + middle initial + first
    if id_middle_init:
        matches = []
        for i, a in enumerate(authors):
            a_first = _normalize(a.first_name)
            a_last = _normalize(a.last_name)
            a_mid_init = ""
            if a.initials and len(a.initials) > 1:
                a_mid_init = a.initials[1].lower()
            else:
                fore_parts = (a.first_name or "").split()
                if len(fore_parts) > 1:
                    a_mid_init = fore_parts[1][0].lower()
                    a_first = _normalize(fore_parts[0])

            if a_last == id_last and a_first == id_first and a_mid_init == id_middle_init:
                matches.append(i)
        if len(matches) == 1:
            return matches[0]

    # Step 3: Exact last + first
    matches = []
    for i, a in enumerate(authors):
        a_first = _normalize(a.first_name)
        a_last = _normalize(a.last_name)
        if a_last == id_last and a_first == id_first:
            matches.append(i)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        best = _disambiguate(matches, authors, identity)
        if best >= 0:
            return best

    # Step 4: Exact last + article first is substring of identity first
    if len(id_first) > 1:
        matches = []
        for i, a in enumerate(authors):
            a_first = _normalize(a.first_name)
            a_last = _normalize(a.last_name)
            if a_last == id_last and a_first and id_first.startswith(a_first) and len(a_first) > 1:
                matches.append(i)
        if len(matches) == 1:
            return matches[0]

    # Step 5: Exact last + identity first is substring of article first
    if len(id_first) > 1:
        matches = []
        for i, a in enumerate(authors):
            a_first = _normalize(a.first_name)
            a_last = _normalize(a.last_name)
            if a_last == id_last and a_first and a_first.startswith(id_first):
                matches.append(i)
        if len(matches) == 1:
            return matches[0]

    # Step 6: Exact last + first initial
    if id_first_init:
        matches = []
        for i, a in enumerate(authors):
            a_last = _normalize(a.last_name)
            a_first_init = _first_initial(a.first_name) or _first_initial(a.initials)
            if a_last == id_last and a_first_init == id_first_init:
                matches.append(i)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            best = _disambiguate(matches, authors, identity)
            if best >= 0:
                return best

    # Step 7: Email match
    if identity.primary_email:
        email_lower = identity.primary_email.lower()
        email_uid = identity.email_uid
        for i, a in enumerate(authors):
            if a.affiliation:
                aff_lower = a.affiliation.lower()
                if email_lower in aff_lower or (email_uid and email_uid in aff_lower):
                    return i

    # Step 8: Swapped first/middle initials
    if id_first_init and id_middle_init:
        matches = []
        for i, a in enumerate(authors):
            a_last = _normalize(a.last_name)
            a_first_init = _first_initial(a.first_name) or _first_initial(a.initials)
            a_mid_init = ""
            if a.initials and len(a.initials) > 1:
                a_mid_init = a.initials[1].lower()
            if (a_last == id_last
                and a_first_init == id_middle_init
                and a_mid_init == id_first_init):
                matches.append(i)
        if len(matches) == 1:
            return matches[0]

    # Step 9: Partial last name + first initial
    if id_first_init and len(id_last) > 2:
        matches = []
        for i, a in enumerate(authors):
            a_last = _normalize(a.last_name)
            a_first_init = _first_initial(a.first_name) or _first_initial(a.initials)
            if id_last in a_last and a_first_init == id_first_init:
                matches.append(i)
        if len(matches) == 1:
            return matches[0]

    # Step 10: Last name exact only
    matches = []
    for i, a in enumerate(authors):
        if _normalize(a.last_name) == id_last:
            matches.append(i)
    if len(matches) == 1:
        return matches[0]

    # Step 11: First name exact only
    if len(id_first) > 1:
        matches = []
        for i, a in enumerate(authors):
            if _normalize(a.first_name) == id_first:
                matches.append(i)
        if len(matches) == 1:
            return matches[0]

    # Step 12: Article last name is substring of identity last name
    if len(id_last) > 3:
        matches = []
        for i, a in enumerate(authors):
            a_last = _normalize(a.last_name)
            if a_last and len(a_last) > 1 and a_last in id_last:
                matches.append(i)
        if len(matches) == 1:
            return matches[0]

    # Step 13: First name exact + last initial
    if len(id_first) > 1:
        id_last_init = _first_initial(identity.last_name)
        matches = []
        for i, a in enumerate(authors):
            a_first = _normalize(a.first_name)
            a_last_init = _first_initial(a.last_name)
            if a_first == id_first and a_last_init == id_last_init:
                matches.append(i)
        if len(matches) == 1:
            return matches[0]

    # Step 14: Middle name → last name match
    if id_middle and len(id_middle) > 1:
        matches = []
        for i, a in enumerate(authors):
            a_last = _normalize(a.last_name)
            a_first_init = _first_initial(a.first_name) or _first_initial(a.initials)
            if a_last == id_middle and a_first_init == id_first_init:
                matches.append(i)
        if len(matches) == 1:
            return matches[0]

    # Step 15: First/last name swap
    if len(id_first) > 1 and len(id_last) > 1:
        matches = []
        for i, a in enumerate(authors):
            a_first = _normalize(a.first_name)
            a_last = _normalize(a.last_name)
            if a_first == id_last and a_last == id_first:
                matches.append(i)
        if len(matches) == 1:
            return matches[0]

    # Step 16-17: lastName→firstName + firstInitial→lastInitial
    if len(id_last) > 1:
        id_last_init = _first_initial(identity.last_name)
        matches = []
        for i, a in enumerate(authors):
            a_first = _normalize(a.first_name)
            a_last_init = _first_initial(a.last_name)
            if len(a_first) > 1 and a_first == id_last and a_last_init == id_first_init:
                matches.append(i)
        if len(matches) == 1:
            return matches[0]

    # Step 18: Both initials match
    if id_first_init:
        id_last_init = _first_initial(identity.last_name)
        matches = []
        for i, a in enumerate(authors):
            a_first_init = _first_initial(a.first_name) or _first_initial(a.initials)
            a_last_init = _first_initial(a.last_name)
            if a_first_init == id_first_init and a_last_init == id_last_init:
                matches.append(i)
        if len(matches) == 1:
            return matches[0]

    # Step 19: Fuzzy last name + first initial or first name match
    if len(id_last) >= 4:
        matches = []
        for i, a in enumerate(authors):
            a_last = _normalize(a.last_name)
            if len(a_last) >= 4:
                dist = levenshtein_distance(a_last, id_last)
                if 0 < dist <= 2:
                    a_first_init = _first_initial(a.first_name) or _first_initial(a.initials)
                    a_first = _normalize(a.first_name)
                    if a_first_init == id_first_init or (len(a_first) > 1 and a_first == id_first):
                        matches.append(i)
        if len(matches) == 1:
            return matches[0]

    return -1


def _disambiguate(
    match_indices: List[int],
    authors: List[Author],
    identity: Identity,
) -> int:
    """
    When multiple authors match, score each on match quality:
    +3 for exact first name, +1 for first initial only,
    +2 for exact middle name, +1 for middle initial only.
    Return best if unique winner, else -1.
    """
    id_first = _normalize(identity.first_name)
    id_middle = _normalize(identity.middle_name)

    scores = {}
    for idx in match_indices:
        a = authors[idx]
        score = 0

        a_first = _normalize(a.first_name)
        if len(a_first) > 1 and a_first == id_first:
            score += 3
        elif _first_initial(a.first_name) == _first_initial(identity.first_name):
            score += 1

        # Middle name
        if id_middle:
            a_mid = ""
            fore_parts = (a.first_name or "").split()
            if len(fore_parts) > 1:
                a_mid = _normalize(" ".join(fore_parts[1:]))
            elif a.initials and len(a.initials) > 1:
                a_mid = a.initials[1].lower()

            if len(a_mid) > 1 and a_mid == id_middle:
                score += 2
            elif a_mid and a_mid[0] == id_middle[0]:
                score += 1

        scores[idx] = score

    if not scores:
        return -1

    max_score = max(scores.values())
    if max_score <= 0:
        return -1

    winners = [idx for idx, s in scores.items() if s == max_score]
    if len(winners) == 1:
        return winners[0]

    return -1
