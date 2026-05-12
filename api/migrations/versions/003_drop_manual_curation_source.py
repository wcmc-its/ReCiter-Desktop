"""Drop unused 'manual' value from curation.source enum

Revision ID: 003
Revises: 002
Create Date: 2026-05-12

The 'manual' enum value was reserved for a Curate page that does not
exist in the current codebase. Every code path that inserts a curation
sets source='import' (assertion imports and gold-standard imports). The
unused value is dropped to keep the schema and the code honest.

Idempotent: the migration is a no-op when the enum is already narrowed,
so re-running on an already-migrated DB is safe.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def _curation_source_type(conn) -> str | None:
    inspector = inspect(conn)
    if 'curation' not in inspector.get_table_names():
        return None
    for col in inspector.get_columns('curation'):
        if col['name'] == 'source':
            return str(col['type'])
    return None


def upgrade() -> None:
    conn = op.get_bind()
    current = _curation_source_type(conn)
    if current is None:
        return
    if "'manual'" not in current.lower() and 'manual' not in current.lower():
        return
    # Defensive: any row that ended up with 'manual' (none exist in normal
    # operation, but treat them as 'import' so the ALTER does not error).
    conn.execute(sa.text("UPDATE curation SET source = 'import' WHERE source = 'manual'"))
    op.alter_column(
        'curation',
        'source',
        type_=sa.Enum('import'),
        existing_type=sa.Enum('import', 'manual'),
        existing_server_default=sa.text("'import'"),
    )


def downgrade() -> None:
    op.alter_column(
        'curation',
        'source',
        type_=sa.Enum('import', 'manual'),
        existing_type=sa.Enum('import'),
        existing_server_default=sa.text("'import'"),
    )
