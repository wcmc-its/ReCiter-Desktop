"""Tests for target author selection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.article import Article, Author
from core.identity import Identity
from core.target_author import identify_target_author


def _make_identity(first="Paul", middle="", last="Albert", email=""):
    return Identity(
        person_id="test", first_name=first, middle_name=middle,
        last_name=last, primary_email=email,
    )


def test_exact_last_first():
    identity = _make_identity(first="Paul", last="Albert")
    article = Article(
        pmid=1,
        authors=[
            Author(first_name="John", last_name="Smith", rank=1),
            Author(first_name="Paul", last_name="Albert", rank=2),
        ],
    )
    assert identify_target_author(article, identity) == 1


def test_initial_match():
    identity = _make_identity(first="Paul", last="Albert")
    article = Article(
        pmid=1,
        authors=[
            Author(first_name="P", last_name="Albert", initials="P", rank=1),
        ],
    )
    assert identify_target_author(article, identity) == 0


def test_no_match():
    identity = _make_identity(first="Paul", last="Albert")
    article = Article(
        pmid=1,
        authors=[
            Author(first_name="John", last_name="Smith", rank=1),
            Author(first_name="Jane", last_name="Doe", rank=2),
        ],
    )
    assert identify_target_author(article, identity) == -1


def test_email_match():
    identity = _make_identity(first="Xyzzy", last="Qwerty", email="xq@med.cornell.edu")
    article = Article(
        pmid=1,
        authors=[
            Author(first_name="X", last_name="Qwert", rank=1,
                   affiliation="Contact: xq@med.cornell.edu"),
        ],
    )
    assert identify_target_author(article, identity) == 0


def test_case_insensitive():
    identity = _make_identity(first="paul", last="albert")
    article = Article(
        pmid=1,
        authors=[Author(first_name="PAUL", last_name="ALBERT", rank=1)],
    )
    assert identify_target_author(article, identity) == 0


def test_name_swap():
    identity = _make_identity(first="Paul", last="Albert")
    article = Article(
        pmid=1,
        authors=[Author(first_name="Albert", last_name="Paul", rank=1)],
    )
    assert identify_target_author(article, identity) == 0


def test_empty_authors():
    identity = _make_identity()
    article = Article(pmid=1, authors=[])
    assert identify_target_author(article, identity) == -1


def test_fuzzy_last_name():
    identity = _make_identity(first="Paul", last="Albert")
    article = Article(
        pmid=1,
        authors=[Author(first_name="Paul", last_name="Alber", rank=1)],
    )
    # Step 19: fuzzy last name (Levenshtein ≤ 2) + first initial match
    assert identify_target_author(article, identity) == 0


if __name__ == "__main__":
    test_exact_last_first()
    test_initial_match()
    test_no_match()
    test_email_match()
    test_case_insensitive()
    test_name_swap()
    test_empty_authors()
    test_fuzzy_last_name()
    print("All target author tests passed!")
