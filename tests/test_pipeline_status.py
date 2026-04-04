"""
Unit tests for assertion_count query in api/routers/pipeline.py

All tests use an in-memory SQLite database -- no Docker required.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.database import Base
from api.models import PersonArticleScore, Curation, Identity, Article, PersonArticle


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_assertion_count_no_curations(db_session):
    """When PersonArticleScore and Curation tables have no joined pairs, assertion_count is 0."""
    from api.routers.pipeline import get_assertion_count

    result = get_assertion_count(db_session)

    assert result == 0


def test_assertion_count_with_curations(db_session):
    """When 3 distinct (person_id, pmid) pairs exist in both tables, assertion_count is 3."""
    from api.routers.pipeline import get_assertion_count

    # Insert 3 Identity rows
    for i in range(1, 4):
        db_session.add(Identity(
            person_id=f"p{i}",
            first_name=f"First{i}",
            last_name=f"Last{i}",
        ))

    # Insert 3 Article rows
    for i in range(1, 4):
        db_session.add(Article(pmid=str(i), title=f"Article {i}"))

    # Insert 3 PersonArticle rows
    for i in range(1, 4):
        db_session.add(PersonArticle(person_id=f"p{i}", pmid=str(i)))

    # Insert 3 PersonArticleScore rows (one per pair, identityOnly)
    for i in range(1, 4):
        db_session.add(PersonArticleScore(
            person_id=f"p{i}",
            pmid=str(i),
            model_type="identityOnly",
            calibrated_score=0.8,
        ))

    # Insert 3 Curation rows (one per pair, ACCEPTED)
    for i in range(1, 4):
        db_session.add(Curation(
            person_id=f"p{i}",
            pmid=str(i),
            assertion="ACCEPTED",
        ))

    db_session.commit()

    result = get_assertion_count(db_session)

    assert result == 3


def test_assertion_count_distinct(db_session):
    """
    When one (person_id, pmid) has two model_type rows in PersonArticleScore
    (identityOnly + feedbackIdentity) but one Curation row, assertion_count
    counts that pair once (not twice).
    """
    from api.routers.pipeline import get_assertion_count

    # Insert 1 Identity
    db_session.add(Identity(person_id="p1", first_name="First", last_name="Last"))

    # Insert 1 Article
    db_session.add(Article(pmid="100", title="Test Article"))

    # Insert 1 PersonArticle
    db_session.add(PersonArticle(person_id="p1", pmid="100"))

    # Insert 2 PersonArticleScore rows for same (person_id, pmid) with different model_type
    db_session.add(PersonArticleScore(
        person_id="p1",
        pmid="100",
        model_type="identityOnly",
        calibrated_score=0.7,
    ))
    db_session.add(PersonArticleScore(
        person_id="p1",
        pmid="100",
        model_type="feedbackIdentity",
        calibrated_score=0.75,
    ))

    # Insert 1 Curation row
    db_session.add(Curation(person_id="p1", pmid="100", assertion="ACCEPTED"))

    db_session.commit()

    result = get_assertion_count(db_session)

    assert result == 1
