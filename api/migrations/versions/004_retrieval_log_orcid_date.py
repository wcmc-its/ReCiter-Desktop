"""Add last_orcid_retrieval_date to retrieval_log

Revision ID: 004
Revises: 003
Create Date: 2026-05-13

The asserted-ORCID retrieval path (commit 3102f0c) unions PMIDs from
an [auid] query into the candidate set. For incremental update runs,
the ORCID query also applies the mindate filter — which silently
skips a researcher's entire pre-mindate ORCID history when their
ORCID was added to the identity record AFTER their first pipeline run.

This migration adds last_orcid_retrieval_date (nullable TIMESTAMP) to
retrieval_log so the pipeline can detect first-time ORCID retrieval
for a person and skip the date filter on that one call.

Idempotent: no-op when the column already exists.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def _has_column(conn, table: str, column: str) -> bool:
    inspector = inspect(conn)
    if table not in inspector.get_table_names():
        return False
    return any(c['name'] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    conn = op.get_bind()
    if _has_column(conn, 'retrieval_log', 'last_orcid_retrieval_date'):
        return
    op.add_column(
        'retrieval_log',
        sa.Column('last_orcid_retrieval_date', sa.TIMESTAMP(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('retrieval_log', 'last_orcid_retrieval_date')
