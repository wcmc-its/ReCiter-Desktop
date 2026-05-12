"""Add article_import_run table

Revision ID: 004
Revises: 003
Create Date: 2026-05-12

Records the lifecycle of a /api/articles/import call so an aborted or
failed import does not leave a partial batch committed with no UI
indication. Mirrors the pipeline_run design (issue #14).

Idempotent: the create is reflection-guarded so a partial run that
crashed mid-migration can be retried.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def _has_table(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if not _has_table(inspector, 'article_import_run'):
        op.create_table(
            'article_import_run',
            sa.Column('run_id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column(
                'status',
                sa.Enum('RUNNING', 'COMPLETED', 'PARTIAL', 'FAILED'),
                nullable=False,
                server_default='RUNNING',
            ),
            sa.Column('total_pmids', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('imported_pmids', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('person_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('file_id', sa.String(64), nullable=True),
            sa.Column('filename', sa.String(512), nullable=True),
            sa.Column('mappings_json', sa.JSON(), nullable=True),
            sa.Column('import_gold_standard', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('started_at', sa.TIMESTAMP(), nullable=True),
            sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('run_id'),
        )


def downgrade() -> None:
    op.drop_table('article_import_run')
