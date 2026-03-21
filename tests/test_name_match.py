"""Tests for name matching feature computation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.article import Article, Author
from core.identity import Identity
from core.config import load_config
from features.name_match import compute_name_scores


config = load_config()


def _make_article(first_name="", last_name="", initials=""):
    article = Article(
        pmid=1,
        authors=[Author(first_name=first_name, last_name=last_name, initials=initials, rank=1)],
    )
    article.target_author_index = 0
    return article


def _make_identity(first_name="John", middle_name="", last_name="Smith"):
    return Identity(person_id="test", first_name=first_name, middle_name=middle_name, last_name=last_name)


def test_first_name_exact_match():
    identity = _make_identity(first_name="Robert", last_name="Smith")
    article = _make_article(first_name="Robert", last_name="Smith")
    scores = compute_name_scores(article, identity, config)
    assert scores["nameMatchFirstScore"] == 1.852


def test_first_name_initial_match():
    identity = _make_identity(first_name="Robert", last_name="Smith")
    article = _make_article(first_name="R", last_name="Smith")
    scores = compute_name_scores(article, identity, config)
    assert scores["nameMatchFirstScore"] == 0.441


def test_first_name_no_match():
    identity = _make_identity(first_name="Robert", last_name="Smith")
    article = _make_article(first_name="Alice", last_name="Smith")
    scores = compute_name_scores(article, identity, config)
    assert scores["nameMatchFirstScore"] == -3.087


def test_first_name_conflicting_all_but_initials():
    identity = _make_identity(first_name="Robert", last_name="Smith")
    article = _make_article(first_name="Richard", last_name="Smith")
    scores = compute_name_scores(article, identity, config)
    assert scores["nameMatchFirstScore"] == -2.646


def test_last_name_exact():
    identity = _make_identity(first_name="John", last_name="Smith")
    article = _make_article(first_name="John", last_name="Smith")
    scores = compute_name_scores(article, identity, config)
    assert scores["nameMatchLastScore"] == 0.664


def test_last_name_conflicting():
    identity = _make_identity(first_name="John", last_name="Smith")
    article = _make_article(first_name="John", last_name="Jones")
    scores = compute_name_scores(article, identity, config)
    assert scores["nameMatchLastScore"] == -0.996


def test_middle_name_exact():
    identity = _make_identity(first_name="John", middle_name="William", last_name="Smith")
    article = Article(
        pmid=1,
        authors=[Author(first_name="John William", last_name="Smith", rank=1)],
    )
    article.target_author_index = 0
    scores = compute_name_scores(article, identity, config)
    assert scores["nameMatchMiddleScore"] == 1.588


def test_middle_name_identity_null():
    identity = _make_identity(first_name="John", middle_name="", last_name="Smith")
    article = _make_article(first_name="John", last_name="Smith")
    scores = compute_name_scores(article, identity, config)
    assert scores["nameMatchMiddleScore"] == 0.794


def test_no_target_author():
    identity = _make_identity()
    article = Article(pmid=1, authors=[Author(first_name="Alice", last_name="Wang", rank=1)])
    article.target_author_index = -1  # no target author
    scores = compute_name_scores(article, identity, config)
    assert scores["nameMatchFirstScore"] == -1.323
    assert scores["nameMatchLastScore"] == -0.996


def test_fuzzy_first_name():
    identity = _make_identity(first_name="Robert", last_name="Smith")
    article = _make_article(first_name="Robet", last_name="Smith")  # typo
    scores = compute_name_scores(article, identity, config)
    assert scores["nameMatchFirstScore"] == -0.75  # full-fuzzy


if __name__ == "__main__":
    test_first_name_exact_match()
    test_first_name_initial_match()
    test_first_name_no_match()
    test_first_name_conflicting_all_but_initials()
    test_last_name_exact()
    test_last_name_conflicting()
    test_middle_name_exact()
    test_middle_name_identity_null()
    test_no_target_author()
    test_fuzzy_first_name()
    print("All name match tests passed!")
