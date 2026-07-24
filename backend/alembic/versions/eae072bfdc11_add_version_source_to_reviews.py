"""add_version_source_to_reviews

Revision ID: eae072bfdc11
Revises: a3f1c8d9e201
Create Date: 2026-07-23 19:11:54.670637

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'eae072bfdc11'
down_revision: Union[str, None] = 'a3f1c8d9e201'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('reviews', sa.Column(
        'version_source',
        sa.String(),
        nullable=True,
        comment="'provided' = from Google Play API, 'inferred' = derived from date timeline, 'unknown' = no data"
    ))
    # Backfill: all existing reviews with a version value are 'provided'
    op.execute("UPDATE reviews SET version_source = 'provided' WHERE version IS NOT NULL")
    # Reviews without version and without date cannot be inferred
    op.execute("UPDATE reviews SET version_source = 'unknown' WHERE version IS NULL AND reviewed_at IS NULL")
    # Reviews without version but with date stay NULL — the pipeline inference step will fill them


def downgrade() -> None:
    op.drop_column('reviews', 'version_source')
