"""Baseline schema snapshot (no-op upgrade — schema already created by schema.sql)

Revision ID: 001
Revises:
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Schema already exists from schema.sql on first install.
    # This migration is a no-op that stamps the version tracker.
    pass


def downgrade() -> None:
    # Drop all tables in reverse dependency order.
    op.drop_table('curation')
    op.drop_table('retrieval_log')
    op.drop_table('person_article_score')
    op.drop_table('person_article')
    op.drop_table('article')
    op.drop_table('identity')
    op.drop_table('institution')
