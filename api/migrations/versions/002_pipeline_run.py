"""Add pipeline_run table, run_id FK columns, and backfill existing rows

Revision ID: 002
Revises: 001
Create Date: 2026-04-06

Idempotent: each schema change is reflection-guarded so a partial run
that crashed mid-migration (e.g. server kill, DB hiccup) can be retried
without "table already exists" / "duplicate column" errors.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def _has_table(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _has_column(inspector, table: str, column: str) -> bool:
    if not _has_table(inspector, table):
        return False
    return any(c["name"] == column for c in inspector.get_columns(table))


def _has_fk(inspector, table: str, name: str) -> bool:
    if not _has_table(inspector, table):
        return False
    return any(fk.get("name") == name for fk in inspector.get_foreign_keys(table))


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    # 1. Create the pipeline_run table (skip if already present)
    if not _has_table(inspector, 'pipeline_run'):
        op.create_table(
            'pipeline_run',
            sa.Column('run_id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('mode', sa.Enum('full', 'update', 'score_only'), nullable=False),
            sa.Column(
                'status',
                sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'PARTIAL', 'FAILED'),
                nullable=False,
                server_default='PENDING',
            ),
            sa.Column('total_researchers', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_articles', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('researchers_succeeded', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('researchers_failed', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('started_at', sa.TIMESTAMP(), nullable=True),
            sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('run_id'),
        )
        # Refresh the inspector so later checks see the new table
        inspector = inspect(conn)

    # 2-3. Seed synthetic run #1 if not already present
    existing_run_1 = conn.execute(
        sa.text("SELECT run_id FROM pipeline_run WHERE run_id = 1")
    ).fetchone()
    if existing_run_1 is None:
        if _has_table(inspector, 'person_article_score'):
            result = conn.execute(
                sa.text(
                    "SELECT MIN(scored_at), MAX(scored_at), COUNT(DISTINCT person_id) "
                    "FROM person_article_score"
                )
            ).fetchone()
            min_ts, max_ts, researcher_count = result[0], result[1], result[2]
        else:
            min_ts, max_ts, researcher_count = None, None, 0

        if min_ts is not None:
            conn.execute(
                sa.text(
                    "INSERT INTO pipeline_run "
                    "(run_id, mode, status, total_researchers, researchers_succeeded, "
                    "researchers_failed, total_articles, started_at, completed_at) "
                    "VALUES (1, 'full', 'COMPLETED', :rc, :rc, 0, 0, :min_ts, :max_ts)"
                ),
                {"rc": researcher_count, "min_ts": min_ts, "max_ts": max_ts},
            )
        else:
            conn.execute(
                sa.text(
                    "INSERT INTO pipeline_run "
                    "(run_id, mode, status, total_researchers, researchers_succeeded, "
                    "researchers_failed, total_articles) "
                    "VALUES (1, 'full', 'COMPLETED', 0, 0, 0, 0)"
                )
            )

    # 4. Add run_id column to person_article_score
    if _has_table(inspector, 'person_article_score'):
        if not _has_column(inspector, 'person_article_score', 'run_id'):
            op.add_column(
                'person_article_score',
                sa.Column('run_id', sa.Integer(), nullable=True),
            )
        if not _has_fk(inspector, 'person_article_score', 'fk_pas_run_id'):
            op.create_foreign_key(
                'fk_pas_run_id',
                'person_article_score',
                'pipeline_run',
                ['run_id'],
                ['run_id'],
                ondelete='SET NULL',
            )
        conn.execute(
            sa.text("UPDATE person_article_score SET run_id = 1 WHERE run_id IS NULL")
        )

    # 5. Add run_id column to retrieval_log
    if _has_table(inspector, 'retrieval_log'):
        if not _has_column(inspector, 'retrieval_log', 'run_id'):
            op.add_column(
                'retrieval_log',
                sa.Column('run_id', sa.Integer(), nullable=True),
            )
        if not _has_fk(inspector, 'retrieval_log', 'fk_rl_run_id'):
            op.create_foreign_key(
                'fk_rl_run_id',
                'retrieval_log',
                'pipeline_run',
                ['run_id'],
                ['run_id'],
                ondelete='SET NULL',
            )
        conn.execute(
            sa.text("UPDATE retrieval_log SET run_id = 1 WHERE run_id IS NULL")
        )


def downgrade() -> None:
    # Drop in reverse order of creation
    op.drop_constraint('fk_rl_run_id', 'retrieval_log', type_='foreignkey')
    op.drop_column('retrieval_log', 'run_id')

    op.drop_constraint('fk_pas_run_id', 'person_article_score', type_='foreignkey')
    op.drop_column('person_article_score', 'run_id')

    op.drop_table('pipeline_run')
