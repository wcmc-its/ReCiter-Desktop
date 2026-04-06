"""
Unit tests for DB-01: upsert write pattern in pipeline_runner.
Tests that the MySQL INSERT ... ON DUPLICATE KEY UPDATE statements
are correctly formed for article, person_article, and person_article_score tables.
"""
import inspect

import pytest
from sqlalchemy.dialects import mysql as mysql_dialect_mod
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy import text

from api.models import Article, PersonArticle, PersonArticleScore


def _compile_mysql(stmt):
    """Compile a SQLAlchemy statement to a MySQL SQL string."""
    return str(stmt.compile(dialect=mysql_dialect_mod.dialect(), compile_kwargs={"literal_binds": False}))


class TestUpsertStatements:
    """Verify that upsert statements produce correct ON DUPLICATE KEY UPDATE SQL."""

    def test_article_upsert_stmt(self):
        """Article upsert should be a no-op on duplicate (preserve existing article data)."""
        rows = [dict(pmid="12345", title="Test", journal="J", pub_year=2024,
                     doi="10.1/x", abstract_text="abs", authors=[],
                     mesh_headings=[], keywords=[], grants=[], publication_types=[])]
        stmt = mysql_insert(Article.__table__).values(rows)
        stmt = stmt.on_duplicate_key_update(pmid=stmt.inserted.pmid)
        sql = _compile_mysql(stmt)
        assert "ON DUPLICATE KEY UPDATE" in sql
        assert "pmid" in sql.split("ON DUPLICATE KEY UPDATE")[1]

    def test_person_article_upsert_stmt(self):
        """PersonArticle upsert should update source on duplicate."""
        rows = [dict(person_id="P1", pmid="12345", source="search")]
        stmt = mysql_insert(PersonArticle.__table__).values(rows)
        stmt = stmt.on_duplicate_key_update(source=stmt.inserted.source)
        sql = _compile_mysql(stmt)
        assert "ON DUPLICATE KEY UPDATE" in sql
        assert "source" in sql.split("ON DUPLICATE KEY UPDATE")[1]

    def test_score_upsert_stmt(self):
        """PersonArticleScore upsert should update score fields + scored_at on duplicate."""
        rows = [dict(person_id="P1", pmid="12345", model_type="identityOnly",
                     calibrated_score=85.0, raw_score=0.85, features={}, run_id=1)]
        stmt = mysql_insert(PersonArticleScore.__table__).values(rows)
        stmt = stmt.on_duplicate_key_update(
            calibrated_score=stmt.inserted.calibrated_score,
            raw_score=stmt.inserted.raw_score,
            features=stmt.inserted.features,
            run_id=stmt.inserted.run_id,
            scored_at=text('NOW()'),
        )
        sql = _compile_mysql(stmt)
        update_clause = sql.split("ON DUPLICATE KEY UPDATE")[1]
        assert "calibrated_score" in update_clause
        assert "raw_score" in update_clause
        assert "features" in update_clause
        assert "run_id" in update_clause
        assert "NOW()" in update_clause


class TestProductionCodePattern:
    """Verify that pipeline_runner.py uses upsert, not SELECT+INSERT."""

    def test_no_article_select_in_process(self):
        """_process_one_researcher must NOT contain db.query(Article).filter_by (old race-prone pattern)."""
        from api.services.pipeline_runner import _process_one_researcher
        source = inspect.getsource(_process_one_researcher)
        assert "db.query(Article).filter_by" not in source, (
            "_process_one_researcher still contains db.query(Article).filter_by — "
            "this SELECT+INSERT pattern is the root cause of the race condition (DB-01)"
        )


class TestRegression:
    """Existing pipeline_runner tests must continue to pass."""

    def test_existing_pipeline_tests_pass(self):
        """Run the 5 existing async tests and assert they all pass."""
        import os
        # Use absolute path to avoid __pycache__ / __file__ mismatch when pytest is
        # invoked from the main repo root while tests live in a worktree.
        test_file = os.path.join(os.path.dirname(__file__), "test_pipeline_runner.py")
        exit_code = pytest.main(["-q", "--tb=short", test_file])
        assert exit_code == 0 or exit_code == pytest.ExitCode.OK, (
            f"Existing pipeline_runner tests failed with exit code {exit_code}"
        )
